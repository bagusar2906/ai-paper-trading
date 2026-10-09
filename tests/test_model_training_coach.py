import copy
import json
from types import SimpleNamespace

import pytest
import requests

from app.services.model_training_coach_service import ModelTrainingCoachService
from app.services.training_coach_evidence import collect_reports, fresh_boundary, persistence


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def fixture():
    settings = {"symbol": "XAUUSD", "timeframe": "M5", "data_source": "yahoo", "bars": 5000,
                "feature_set_id": "raw-ohlcv-v1", "horizon_candles": 12, "up_return_threshold": .003,
                "n_estimators": 100, "max_depth": 3, "learning_rate": .05, "probability_threshold": .5,
                "replace_previous_candidate": False}
    def scores(auc, brier, skill, beats):
        return {"roc_auc": auc, "brier_score": brier, "log_loss": .3,
                "brier_skill": skill, "beats_baseline": beats, "positive_predictions": 0}
    report = {"experiment_id": "exp", "model_id": "selected", "status": "completed", "samples": 100,
              "market_context": {key: settings[key] for key in ("symbol", "timeframe", "data_source")},
              "label_definition_id": "future_return_up-n12-t0.003", "purge_candles": 12,
              "evaluation_start": "2026-01-02T00:00:00Z", "evaluation_end": "2026-01-02T10:00:00Z",
              "outcome_end_time": "2026-01-02T11:00:00Z",
              "baseline": {direction: {"probability": .08, "observed_rate": .07} for direction in ("up", "down")},
              "results": [
                  {"model_id": "selected", "recipe": "current-recipe", "status": "completed", "parameters": settings,
                   "scores": {"up": scores(.42, .075, -.05, False), "down": scores(.58, .09, .1, True)}},
                  {"model_id": "core", "recipe": "feature-check", "status": "completed",
                   "parameters": settings | {"feature_set_id": "core-v1"},
                   "scores": {"up": scores(.65, .064, .085, True), "down": scores(.71, .095, .05, True)}},
              ]}
    models = {}
    for row in report["results"]:
        metadata = {"training_request": row["parameters"], "controlled_experiment": {"experiment_id": "exp"},
                    "market_context": report["market_context"],
                    "review_history": [{"type": "controlled_experiment", "evidence": copy.deepcopy(report)}]}
        models[row["model_id"]] = SimpleNamespace(model_id=row["model_id"], metadata_json=json.dumps(metadata),
            status="candidate", feature_set_id=row["parameters"]["feature_set_id"], label_definition_id=report["label_definition_id"])
    closed, events = [], []
    def save(model_id, kind, evidence):
        metadata = json.loads(models[model_id].metadata_json)
        metadata["review_history"].append({"type": kind, "evidence": copy.deepcopy(evidence)})
        models[model_id].metadata_json = json.dumps(metadata)
        events.append((model_id, kind))
    registry = SimpleNamespace(get=lambda key: models.get(key), get_all=lambda: list(models.values()),
        add_review_event=save, review_history=lambda key: json.loads(models[key].metadata_json)["review_history"])
    repos = SimpleNamespace(model_registry=registry, close=lambda: closed.append(True))
    return models, repos, settings, report, events


def test_local_coach_diagnoses_tradeoffs_and_keeps_recommendations_bounded():
    models, repos, settings, _, events = fixture()
    report = ModelTrainingCoachService(lambda: repos).review("selected")
    assert report["source"] == "local_evidence"
    assert any("No recipe produced" in finding for finding in report["findings"])
    assert any("ranking but worsens Brier" in finding for finding in report["findings"])
    assert report["plan"]["fresh_after"] == "2026-01-02T11:00:00+00:00"
    assert 2 <= len(report["plan"]["variants"]) <= 4
    variants = report["plan"]["variants"]
    assert len({json.dumps(variant["parameters"], sort_keys=True) for variant in variants}) == len(variants)
    for variant in variants:
        p = variant["parameters"]
        assert p["horizon_candles"] == 12 and p["up_return_threshold"] == .003 and p["probability_threshold"] == .5
        assert 25 <= p["n_estimators"] <= 500 and 1 <= p["max_depth"] <= 8 and .01 <= p["learning_rate"] <= .3
        assert p["bars"] == 5000 and p["data_source"] == "yahoo"
        assert p["replace_previous_candidate"] is False
    assert not report["automatic_promotion"] and not report["automatic_training"]
    assert report["history_saved"] and events
    assert all(model.status == "candidate" for model in models.values())
    assert all(row["fresh_periods"] == 0 for row in report["tracking"])
    json.dumps(report, allow_nan=False)


def test_ai_selects_only_allowed_recipes_and_receives_saved_evidence(monkeypatch):
    _, repos, _, _, _ = fixture()
    monkeypatch.setenv("AI_API_KEY", "test-key")
    sent = {}
    def requester(url, **kwargs):
        sent.update(url=url, **kwargs)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"output_text": json.dumps({
            "summary": "Investigate probability quality.", "reasoning": ["Consider the DOWN tradeoff."],
            "caveats": ["Fresh validation is needed."], "recommended_ids": ["slower-learning"]})})
    report = ModelTrainingCoachService(lambda: repos, requester).review("selected")
    assert report["source"] == "ai"
    assert [variant["id"] for variant in report["plan"]["variants"]] == ["current-recipe", "slower-learning"]
    request = sent["json"]
    assert request["store"] is False and request["text"]["format"]["strict"] is True
    assert json.loads(request["input"])["recipes"][0]["scores"]["up"]["roc_auc"] == .42
    assert "test-key" not in request["input"]


@pytest.mark.parametrize("failure", ["unknown", "duplicate", "too_many", "parameters", "connection", "invalid_json"])
def test_invalid_ai_output_falls_back_without_expanding_scope(monkeypatch, failure):
    _, repos, _, _, _ = fixture()
    monkeypatch.setenv("AI_API_KEY", "test-key")
    def requester(*args, **kwargs):
        if failure == "connection":
            raise requests.ConnectionError("offline")
        choices = {"unknown": ["set-threshold-to-zero"], "duplicate": ["feature-check", "feature-check"],
                   "too_many": ["feature-check", "slower-learning", "simpler-trees", "more-capacity"]}.get(failure, ["slower-learning"])
        value = {"summary": "Advice", "reasoning": [], "caveats": [], "recommended_ids": choices}
        if failure == "parameters":
            value["parameters"] = {"probability_threshold": 0}
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"output_text": "invalid" if failure == "invalid_json" else json.dumps(value)})
    report = ModelTrainingCoachService(lambda: repos, requester).review("selected")
    assert report["source"] == "local_evidence"
    assert "could not return" in report["source_note"]
    assert len(report["plan"]["variants"]) <= 4
    assert all(v["parameters"]["probability_threshold"] == .5 for v in report["plan"]["variants"])


def test_no_shared_experiment_requires_bootstrap_and_does_not_invent_validation():
    models, repos, _, _, _ = fixture()
    for model in models.values():
        metadata = json.loads(model.metadata_json)
        metadata["review_history"] = []
        model.metadata_json = json.dumps(metadata)
    coach = ModelTrainingCoachService(lambda: repos)
    report = coach.review("selected")
    assert report["can_validate"] is False and report["tracking"] == []
    assert "No comparable" in report["findings"][0]
    assert "fresh_after" not in report["plan"]
    with pytest.raises(ValueError, match="controlled experiments first"):
        coach.validate_fresh("selected")


def test_saved_plan_can_run_but_setting_changes_require_a_new_review():
    models, repos, _, _, _ = fixture()
    calls = []
    experiment = SimpleNamespace(run=lambda model_id, **kwargs: calls.append((model_id, kwargs)) or {"status": "waiting_for_fresh_data"})
    coach = ModelTrainingCoachService(lambda: repos, experiment_service=experiment)
    report = coach.review("selected")
    assert coach.run_recommendations("selected", report["coach_id"])["status"] == "waiting_for_fresh_data"
    assert calls[0][1]["plan"]["coach_id"] == report["coach_id"]
    metadata = json.loads(models["selected"].metadata_json)
    metadata["training_request"]["learning_rate"] = .1
    models["selected"].metadata_json = json.dumps(metadata)
    with pytest.raises(ValueError, match="settings changed"):
        coach.run_recommendations("selected", report["coach_id"])
    with pytest.raises(ValueError, match="no longer available"):
        coach.run_recommendations("selected", "missing")
    assert len(calls) == 1


def test_deduplicated_fresh_periods_track_mixed_results_and_ignore_other_markets():
    models, repos, settings, experiment, _ = fixture()
    validation = copy.deepcopy(experiment)
    validation.update(validation_id="fresh-1", evaluation_start="2026-01-03T00:00:00Z",
                      evaluation_end="2026-01-03T10:00:00Z", outcome_end_time="2026-01-03T11:00:00Z")
    validation["results"][1]["scores"]["down"]["beats_baseline"] = False
    foreign = copy.deepcopy(experiment)
    foreign.update(experiment_id="foreign", market_context=experiment["market_context"] | {"data_source": "mt5"})
    for model in models.values():
        metadata = json.loads(model.metadata_json)
        metadata["review_history"].extend([{"type": "fresh_model_validation", "evidence": validation},
                                           {"type": "controlled_experiment", "evidence": foreign}])
        model.metadata_json = json.dumps(metadata)
    experiments, validations = collect_reports(models.values(), settings)
    assert len(experiments) == len(validations) == 1
    tracking = persistence(experiment, validations)
    assert tracking[1]["fresh_periods"] == 1
    assert tracking[1]["status"] == "mixed_or_worse"
    report = ModelTrainingCoachService(lambda: repos).review("selected")
    assert report["plan"]["fresh_after"] == "2026-01-03T11:00:00+00:00"


def test_corrupt_metrics_and_history_do_not_produce_nonfinite_ai_evidence():
    models, repos, _, _, _ = fixture()
    metadata = json.loads(models["selected"].metadata_json)
    metadata["review_history"][0]["evidence"]["results"][0]["scores"]["up"]["roc_auc"] = float("nan")
    metadata["review_history"].append("invalid")
    models["selected"].metadata_json = json.dumps(metadata)
    report = ModelTrainingCoachService(lambda: repos).review("selected")
    json.dumps(report, allow_nan=False)


def test_coach_routes_return_missing_invalid_and_busy_errors(monkeypatch):
    from fastapi import HTTPException
    from app.api import models
    service = SimpleNamespace(review=lambda _: (_ for _ in ()).throw(LookupError("model not found")),
        run_recommendations=lambda *args: (_ for _ in ()).throw(ValueError("stale plan")),
        validate_fresh=lambda _: (_ for _ in ()).throw(RuntimeError("busy")))
    monkeypatch.setattr(models, "ModelTrainingCoachService", lambda: service)
    for action, expected in ((lambda: models.review_training_coach("m"), 404),
                             (lambda: models.run_training_coach("m", {"coach_id": "c"}), 400),
                             (lambda: models.validate_training_coach("m"), 400)):
        with pytest.raises(HTTPException) as error:
            action()
        assert error.value.status_code == expected


def test_default_trading_source_is_resolved_and_provider_changes_require_review():
    models, repos, _, _, _ = fixture()
    metadata = json.loads(models["selected"].metadata_json)
    metadata["training_request"]["data_source"] = "trading"
    models["selected"].metadata_json = json.dumps(metadata)
    source = ["yahoo"]
    repos.settings = SimpleNamespace(get_market_data_provider=lambda: source[0])
    calls = []
    runner = SimpleNamespace(run=lambda model_id, **kwargs: calls.append(kwargs["plan"]) or {"status": "waiting_for_fresh_data"})
    coach = ModelTrainingCoachService(lambda: repos, experiment_service=runner)
    report = coach.review("selected")
    assert report["can_validate"] is True
    assert report["evidence"]["market_context"]["data_source"] == "yahoo"
    assert all(variant["parameters"]["data_source"] == "yahoo" for variant in report["plan"]["variants"])
    coach.run_recommendations("selected", report["coach_id"])
    source[0] = "mt5"
    with pytest.raises(ValueError, match="settings changed"):
        coach.run_recommendations("selected", report["coach_id"])
    assert len(calls) == 1
