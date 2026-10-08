import json
from types import SimpleNamespace

import pytest
import requests
from fastapi import HTTPException

from app.services.model_analysis_service import ModelAnalysisService


def model():
    scores = {"precision": .75, "recall": .4, "roc_auc": .67, "brier_score": .16, "log_loss": .52,
              "reliability_bins": [{"count": 100, "mean_probability": .3, "observed_rate": .25}]}
    metadata = {"training_config": {"probability_threshold": .6},
                "folds": [{"metrics": {"roc_auc": .55}}, {"metrics": {"roc_auc": .79}}],
                "feature_importance": [{"feature": "close_lag_1", "importance": .2}]}
    return SimpleNamespace(model_id="m1", status="candidate", feature_set_id="raw-ohlcv-v1",
                           label_definition_id="future_return_up-n12-t0.003",
                           metrics_json=json.dumps(scores), metadata_json=json.dumps(metadata))


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_local_analysis_explains_actual_evidence_and_its_limits():
    report = ModelAnalysisService().analyze(model())
    assert report["source"] == "local_evidence"
    assert report["automatic_promotion"] is False
    assert "75.0%" in report["metrics"][0]["explanation"]
    assert "40.0%" in report["metrics"][1]["explanation"]
    evidence = report["evidence"]
    assert "0.30% after 12 candles" in evidence["target"]
    assert evidence["probability_threshold"] == .6
    assert evidence["validation_observations"] == 100
    assert evidence["fold_ranges"]["roc_auc"] == {"min": .55, "max": .79, "folds_with_score": 2}
    assert any("not an independent test" in note for note in report["evidence_notes"])
    assert model().status == "candidate"


@pytest.mark.parametrize("metadata,metrics", [("[]", "null"), ("broken", "{}"), ("{}", '{"precision": NaN}')])
def test_legacy_or_invalid_evidence_remains_readable(metadata, metrics):
    item = model()
    item.metadata_json, item.metrics_json = metadata, metrics
    report = ModelAnalysisService().analyze(item)
    assert report["metrics"][0]["value"] is None
    assert any("incomplete" in note for note in report["evidence_notes"])
    json.dumps(report, allow_nan=False)


def test_zero_precision_is_not_claimed_to_be_all_wrong():
    item = model()
    item.metrics_json = '{"precision": 0, "recall": 0}'
    report = ModelAnalysisService().analyze(item)
    assert "no positive predictions" in report["metrics"][0]["explanation"]
    assert "About 0" not in report["metrics"][0]["explanation"]


def test_directional_analysis_includes_downside_scores_and_neutral_target():
    item = model()
    scores = json.loads(item.metrics_json)
    scores["downside"] = {"precision": .8, "recall": .5, "roc_auc": .7, "brier_score": .12, "log_loss": .4}
    metadata = json.loads(item.metadata_json)
    metadata["prediction_contract"] = {"outcomes": ["up", "down", "neutral"]}
    item.metrics_json, item.metadata_json = json.dumps(scores), json.dumps(metadata)
    report = ModelAnalysisService().analyze(item)
    assert "smaller moves are neutral" in report["evidence"]["target"]
    assert report["evidence"]["downside_validation_scores"]["precision"] == .8
    down_precision = next(metric for metric in report["metrics"] if metric["key"] == "down_precision")
    assert "DOWN" in down_precision["explanation"]
    assert down_precision["value"] == .8


def test_ai_receives_saved_scores_and_validated_narrative(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_API_BASE_URL", "http://gateway/v1")
    sent = {}
    narrative = {"summary": "Precision is higher than recall.", "strengths": ["Some ranking signal"],
                 "limitations": ["Fold variation"], "next_steps": ["Compare on unseen data"]}
    def requester(url, **kwargs):
        sent.update(url=url, **kwargs)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"output_text": json.dumps(narrative)})
    report = ModelAnalysisService(requester).analyze(model())
    assert report["source"] == "ai"
    assert report["summary"] == narrative["summary"]
    assert sent["url"] == "http://gateway/v1/responses"
    assert sent["json"]["store"] is False
    assert json.loads(sent["json"]["input"])["validation_scores"]["precision"] == .75
    assert report["evidence_notes"]


@pytest.mark.parametrize("failure", ["invalid_schema", "invalid_json", "connection"])
def test_ai_failure_has_honest_local_fallback(monkeypatch, failure):
    monkeypatch.setenv("AI_API_KEY", "test-key")
    def requester(*args, **kwargs):
        if failure == "connection":
            raise requests.ConnectionError("offline")
        text = '{}' if failure == "invalid_schema" else 'not json'
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"output_text": text})
    report = ModelAnalysisService(requester).analyze(model())
    assert report["source"] == "local_evidence"
    assert "could not return" in report["source_note"]


@pytest.mark.parametrize("missing,save_fails", [(False, False), (False, True), (True, False)])
def test_analysis_endpoint_saves_history_without_promoting(monkeypatch, missing, save_fails):
    from app.api import models
    item, events, closed = model(), [], []
    def save(model_id, kind, report):
        if save_fails:
            raise RuntimeError("database failure")
        events.append((model_id, kind, report.copy()))
    repos = SimpleNamespace(model_registry=SimpleNamespace(get=lambda _: None if missing else item, add_review_event=save),
                            close=lambda: closed.append(True))
    monkeypatch.setattr(models, "RepositoryFactory", lambda: repos)
    if missing:
        with pytest.raises(HTTPException) as error:
            models.analyze_model("m1")
        assert error.value.status_code == 404
    else:
        report = models.analyze_model("m1")
        assert report["history_saved"] is not save_fails
        assert len(events) == (0 if save_fails else 1)
        if events:
            assert events[0][1] == "model_analysis"
        assert item.status == "candidate"
    assert closed == [True]
