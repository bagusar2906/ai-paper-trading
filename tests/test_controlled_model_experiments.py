import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app.features.dataset import build_training_dataset
from app.labels.future_return import FutureReturnLabel
from app.ml.evaluation import probability_scores, baseline_comparison
from app.ml.training import CandidateTrainer, CandidateTrainingConfig
from app.services.controlled_model_experiment_service import ControlledModelExperimentService
from app.services.model_training_service import ModelTrainingService
from tests.test_ml_candidate_training import _candles


def setup_service(tmp_path, repos, monkeypatch):
    history = _candles(700)
    settings = {"symbol": "XAUUSD", "timeframe": "M5", "data_source": "yahoo", "bars": 700,
                "feature_set_id": "raw-ohlcv-v1", "horizon_candles": 3, "up_return_threshold": .0001,
                "n_estimators": 25, "max_depth": 2, "learning_rate": .05, "probability_threshold": .5}
    definition = FutureReturnLabel(3, .0001)
    dataset = build_training_dataset(history, definition, "raw-ohlcv-v1")
    result = CandidateTrainer(tmp_path).train(dataset, definition.name, CandidateTrainingConfig(
        walk_forward=ModelTrainingService._walk_forward_config(len(dataset.frame), 3), n_estimators=25))
    result.metadata["training_request"] = settings
    repos.model_registry.record_candidate(result)
    repos.model_registry.promote_candidate(result.model_id, "test", "test reference")
    monkeypatch.setattr(repos, "close", lambda: None)
    calls, training_frames, evaluated = [], [], []
    class Provider:
        source_name = "yahoo"
        disconnected = False
        def get_history(self, *args):
            calls.append(args)
            return history
        def disconnect(self):
            self.disconnected = True
    provider = Provider()
    class Trainer(CandidateTrainer):
        def train(self, dataset, *args):
            training_frames.append(dataset.frame.copy())
            return super().train(dataset, *args)
    service = ControlledModelExperimentService(lambda *_: provider, lambda: repos, Trainer, tmp_path)
    score = service._probabilities
    def probabilities(result, features):
        evaluated.append(features.index.copy())
        return score(result, features)
    monkeypatch.setattr(service, "_probabilities", probabilities)
    return service, result.model_id, history, provider, calls, training_frames, evaluated


def test_real_experiments_share_unseen_rows_and_training_only_baseline(tmp_path, repos, monkeypatch):
    service, selected, history, provider, calls, train, evaluated = setup_service(tmp_path, repos, monkeypatch)
    plan = service.plan(selected)
    assert len(plan["variants"]) == 4
    assert calls == []  # preview never fetches data or trains
    assert {v["parameters"]["feature_set_id"] for v in plan["variants"]} == {"core-v1", "raw-ohlcv-v1"}
    assert all(v["parameters"]["replace_previous_candidate"] is False for v in plan["variants"])
    report = service.run(selected)
    assert report["status"] == "completed", report
    assert provider.disconnected and len(calls) == 1
    assert len(train) == len(evaluated) == 4
    assert all(frame.index.equals(train[0].index) for frame in train)
    assert all(index.equals(evaluated[0]) for index in evaluated)
    first = history.index.get_loc(evaluated[0][0])
    assert (history.index.get_indexer(train[0].index) + 3 < first).all()
    assert report["baseline"]["up"]["probability"] == float(train[0]["future_return_up"].mean())
    assert report["baseline"]["down"]["probability"] == float(train[0]["future_return_down"].mean())
    assert report["history_saved"] and not report["automatic_promotion"]
    families = set()
    for row in report["results"]:
        registered = repos.model_registry.get(row["model_id"])
        assert registered.status == "candidate"
        metadata = json.loads(registered.metadata_json)
        assert metadata["candidate_family"]["origin"] == "controlled_experiment"
        families.add(metadata["candidate_family"]["key"])
        assert repos.model_registry.review_history(row["model_id"])[-1]["evidence"]["experiment_id"] == report["experiment_id"]
        assert metadata["evaluation_window"]["start_time"] == report["evaluation_start"]
        for direction in ("up", "down"):
            scores = row["scores"][direction]
            baseline = report["baseline"][direction]["scores"]
            assert scores["brier_skill"] == pytest.approx(1 - scores["brier_score"] / baseline["brier_score"])
    assert len(families) == 4  # progress must not mix different recipes
    assert repos.model_registry.get(selected).status == "champion"
    saved = repos.model_registry.review_history(selected)[-1]
    assert saved["type"] == "controlled_experiment"
    assert saved["evidence"]["history_saved"] is True
    json.dumps(report, allow_nan=False)


def test_partial_failure_keeps_successful_candidates_and_cleans_failed_artifact(tmp_path, repos, monkeypatch):
    service, selected, _, _, _, _, _ = setup_service(tmp_path, repos, monkeypatch)
    original = repos.model_registry.record_candidate
    count = 0
    def register(result):
        nonlocal count
        count += 1
        if count == 2:
            raise ValueError("registry failure")
        return original(result)
    monkeypatch.setattr(repos.model_registry, "record_candidate", register)
    report = service.run(selected)
    assert report["status"] == "partial"
    assert report["results"][1]["status"] == "failed"
    assert "registry failure" in report["results"][1]["error"]
    assert len(list(tmp_path.glob("*.pkl"))) == 4  # selected + 3 successful fits
    assert not ModelTrainingService._training_lock.locked()


def test_small_dataset_and_fetch_failure_release_lock(tmp_path, repos, monkeypatch):
    service, selected, history, provider, _, _, _ = setup_service(tmp_path, repos, monkeypatch)
    monkeypatch.setattr(provider, "get_history", lambda *_: history.iloc[:250])
    with pytest.raises(ValueError, match="not enough training rows"):
        service.run(selected)
    assert not ModelTrainingService._training_lock.locked()
    def failed(*_):
        raise RuntimeError("source offline")
    monkeypatch.setattr(provider, "get_history", failed)
    with pytest.raises(RuntimeError, match="offline"):
        service.run(selected)
    assert provider.disconnected and not ModelTrainingService._training_lock.locked()


def test_training_lock_prevents_concurrent_experiments():
    ModelTrainingService._training_lock.acquire()
    try:
        with pytest.raises(RuntimeError, match="in progress"):
            ControlledModelExperimentService().run("unused")
    finally:
        ModelTrainingService._training_lock.release()


def test_baseline_skill_zero_single_class_and_invalid_probabilities():
    baseline = probability_scores([0, 1], [.5, .5])
    good = probability_scores([0, 1], [.1, .9])
    assert baseline_comparison(good, baseline) == {"brier_skill": pytest.approx(.96), "beats_baseline": True}
    assert baseline_comparison(baseline, baseline)["brier_skill"] == 0
    zero = probability_scores([0, 0], [0, 0])
    assert zero["roc_auc"] is None
    assert baseline_comparison(zero, zero)["brier_skill"] is None
    assert baseline_comparison(good, None)["beats_baseline"] is None
    assert probability_scores([0, 1], [.1, .2])["positive_predictions"] == 0
    for values in ([np.nan, .5], [1.1, .5], [-.1, .5]):
        with pytest.raises(ValueError):
            probability_scores([0, 1], values)


def test_routes_report_missing_models_and_busy_training(monkeypatch):
    from fastapi import HTTPException
    from app.api import models
    service = SimpleNamespace(plan=lambda _: (_ for _ in ()).throw(LookupError("model not found")),
                              run=lambda _: (_ for _ in ()).throw(RuntimeError("training busy")))
    monkeypatch.setattr(models, "ControlledModelExperimentService", lambda: service)
    with pytest.raises(HTTPException) as error:
        models.controlled_experiment_plan("missing")
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        models.run_controlled_experiments("model")
    assert error.value.status_code == 400
