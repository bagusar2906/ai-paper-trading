import json
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.database.models import ModelVersionEntity, TrainingRunEntity
from app.services.model_training_progress_service import ModelTrainingProgressService


def metadata():
    return {"candidate_family": {"key": "recipe", "origin": "self_training"},
            "market_context": {"symbol": "XAUUSD", "timeframe": "M5", "data_source": "yahoo"},
            "prediction_contract": {"outcomes": ["up", "down", "neutral"]},
            "folds": [{"validation_start": "2026-01-01T00:00:00Z", "validation_end": "2026-01-02T00:00:00Z",
                       "metrics": {"roc_auc": .6}, "down_metrics": {"roc_auc": .7}}]}


def save(repos, number, details=None, *, registered=True, scores=None):
    details = metadata() if details is None else details
    details = {**details, "model_id": f"model-{number}"}
    created = datetime(2026, 1, 1) + timedelta(days=number)
    scores = scores if scores is not None else {"roc_auc": .5 + number / 100, "downside": {"roc_auc": .6}}
    repos.session.add(TrainingRunEntity(
        training_run_id=f"run-{number}", status="completed", feature_set_id="raw-ohlcv-v1",
        label_definition_id="future_return_up-n12-t0.003", config_json="{}",
        metadata_json=json.dumps(details), metrics_json=json.dumps(scores), created_at=created,
    ))
    if registered:
        repos.session.add(ModelVersionEntity(
            model_id=f"model-{number}", training_run_id=f"run-{number}", status="candidate",
            feature_set_id="raw-ohlcv-v1", label_definition_id="future_return_up-n12-t0.003",
            artifact_path="not-loaded.pkl", artifact_sha256="a" * 64,
            metadata_json=json.dumps(details), metrics_json=json.dumps(scores), created_at=created,
        ))
    repos.session.commit()


def service(repos, monkeypatch):
    monkeypatch.setattr(repos, "close", lambda: None)
    return ModelTrainingProgressService(lambda: repos)


def test_history_includes_replaced_candidates_and_excludes_different_setups(repos, monkeypatch):
    save(repos, 1, registered=False)  # Candidate removed; training evidence remains.
    save(repos, 2)
    for number, change in [(3, "origin"), (4, "market"), (5, "contract"), (6, "family")]:
        details = metadata()
        if change == "origin": details["candidate_family"]["origin"] = "manual"
        if change == "market": details["market_context"]["symbol"] = "EURUSD"
        if change == "contract": details.pop("prediction_contract")
        if change == "family": details["candidate_family"]["key"] = "other-recipe"
        save(repos, number, details)
    before = repos.model_registry.get("model-2").metadata_json

    report = service(repos, monkeypatch).get("model-2")

    assert [run["training_run_id"] for run in report["runs"]] == ["run-1", "run-2"]
    assert report["runs"][0]["model_id"] == "model-1"
    assert report["runs"][1]["selected"] is True
    assert report["runs"][0]["created_at"].endswith("+00:00")
    assert report["folds"][0]["metrics"]["down"]["roc_auc"] == .7
    assert repos.model_registry.get("model-2").metadata_json == before
    assert repos.model_registry.get("model-2").status == "candidate"
    json.dumps(report, allow_nan=False)


def test_chart_retains_selected_model_when_history_is_bounded(repos, monkeypatch):
    for number in range(1, 5): save(repos, number)
    worker = service(repos, monkeypatch)
    worker.MAX_RUNS = 2
    report = worker.get("model-1")
    assert report["limited"] is True
    assert len(report["runs"]) == 2
    assert any(run["selected"] and run["model_id"] == "model-1" for run in report["runs"])


def test_legacy_model_without_provenance_does_not_mix_unrelated_history(repos, monkeypatch):
    save(repos, 1, {})
    save(repos, 2, {})
    report = service(repos, monkeypatch).get("model-2")
    assert report["matching_history_available"] is False
    assert [run["training_run_id"] for run in report["runs"]] == ["run-2"]


def test_invalid_scores_are_missing_instead_of_fake_zeroes(repos, monkeypatch):
    details = metadata()
    details["folds"] = [None, {"metrics": {"precision": True, "roc_auc": float("nan")}, "down_metrics": "bad"}]
    save(repos, 1, details, scores={"precision": 0, "roc_auc": float("nan"), "recall": True,
                                 "brier_score": -1, "log_loss": 2.5, "downside": {"precision": 2}})
    report = service(repos, monkeypatch).get("model-1")
    scores = report["runs"][0]["metrics"]
    assert scores["up"]["precision"] == 0
    assert scores["up"]["roc_auc"] is scores["up"]["recall"] is scores["up"]["brier_score"] is None
    assert scores["up"]["log_loss"] == 2.5
    assert scores["down"]["precision"] is None
    assert len(report["folds"]) == 1
    json.dumps(report, allow_nan=False)


def test_selected_model_without_training_record_still_exposes_saved_scores(repos, monkeypatch):
    save(repos, 1)
    repos.session.query(TrainingRunEntity).delete()
    repos.session.commit()
    report = service(repos, monkeypatch).get("model-1")
    assert report["runs"][0]["selected"] is True
    assert report["runs"][0]["metrics"]["up"]["roc_auc"] == .51


def test_progress_missing_model_closes_repository_and_returns_404(repos, monkeypatch):
    closed = []
    monkeypatch.setattr(repos, "close", lambda: closed.append(True))
    worker = ModelTrainingProgressService(lambda: repos)
    with pytest.raises(LookupError): worker.get("missing")
    assert closed == [True]
    from app.api import models
    monkeypatch.setattr(models, "ModelTrainingProgressService", lambda: worker)
    with pytest.raises(HTTPException) as error: models.model_training_progress("missing")
    assert error.value.status_code == 404
