import json
from pathlib import Path

import pandas as pd
import pytest

from app.database.models import TrainingRunEntity
from app.ml.training import CandidateTrainer
from app.services.model_training_service import ModelTrainingService
from app.services.training_data_sync_service import TrainingDataSyncService
from tests.test_model_training_service import _candles


def setup(repos, monkeypatch, tmp_path):
    monkeypatch.setattr(repos, "close", lambda: None)
    data = [_candles(300)]
    class Provider:
        def __init__(self, source="yahoo"):
            self.source_name = source
        def get_history(self, symbol, timeframe, bars):
            return data[0].tail(bars)
        def get_history_range(self, symbol, timeframe, start, end):
            return data[0][(data[0].index >= start) & (data[0].index < end)]
        def disconnect(self):
            pass
    monkeypatch.setattr("app.services.model_training_service.TrainingDataSyncService",
                        lambda factory: TrainingDataSyncService(factory, now=lambda: data[0].index[-1] + pd.Timedelta(minutes=5)))
    service = ModelTrainingService(Provider, lambda: repos, artifact_directory=tmp_path)
    request = {"bars": 300, "horizon_candles": 3, "n_estimators": 25,
               "feature_set_id": "raw-ohlcv-v1", "data_source": "yahoo"}
    return service, request, data


def test_default_replaces_candidate_and_artifacts_but_preserves_training_audit(repos, monkeypatch, tmp_path):
    service, request, data = setup(repos, monkeypatch, tmp_path)
    assert service.validate_request(request)["replace_previous_candidate"] is True
    first = service.train_candidate(request)
    old = repos.model_registry.get(first["model_id"])
    artifact, run_id = Path(old.artifact_path), old.training_run_id
    repos.model_registry.add_review_event(old.model_id, "model_analysis", {"summary": "old report"})
    data[0] = _candles(305)
    second = service.train_candidate(request)
    assert second["replaced_model_ids"] == [first["model_id"]]
    assert repos.model_registry.get(first["model_id"]) is None
    assert len(repos.model_registry.get_all()) == 1
    assert not artifact.exists() and not artifact.with_suffix(".json").exists()
    assert len(list(tmp_path.glob("*.pkl"))) == 1
    old_run = repos.session.get(TrainingRunEntity, run_id)
    assert json.loads(old_run.metadata_json)["review_history"][-1]["type"] == "model_analysis"
    assert repos.model_registry.review_history(second["model_id"])[-1]["type"] == "candidate_replaced"
    assert repos.model_registry.promotion_history()[0].action == "replace_candidate"


def test_keeping_versions_is_optional_and_enabling_replacement_removes_accumulated_family(repos, monkeypatch, tmp_path):
    service, request, data = setup(repos, monkeypatch, tmp_path)
    first = service.train_candidate({**request, "replace_previous_candidate": False})
    data[0] = _candles(305)
    second = service.train_candidate({**request, "replace_previous_candidate": False})
    assert len(repos.model_registry.get_all()) == 2
    # No new data: rolling retention can still prune older candidates.
    duplicate = service.train_candidate(request)
    assert duplicate["status"] == "duplicate"
    assert duplicate["model_id"] == second["model_id"]
    assert duplicate["replaced_model_ids"] == [first["model_id"]]
    assert len(repos.model_registry.get_all()) == 1


def test_training_failure_keeps_previous_candidate(repos, monkeypatch, tmp_path):
    service, request, data = setup(repos, monkeypatch, tmp_path)
    first = service.train_candidate(request)
    old_path = Path(repos.model_registry.get(first["model_id"]).artifact_path)
    data[0] = _candles(305)
    class FailingTrainer:
        def __init__(self, *args, **kwargs):
            pass
        def train(self, *args):
            raise RuntimeError("training failed")
    service.trainer_factory = FailingTrainer
    with pytest.raises(RuntimeError, match="training failed"):
        service.train_candidate(request)
    assert repos.model_registry.get(first["model_id"]).status == "candidate"
    assert old_path.exists()


def test_bad_new_artifact_cannot_replace_previous_candidate(repos, monkeypatch, tmp_path):
    service, request, data = setup(repos, monkeypatch, tmp_path)
    first = service.train_candidate(request)
    data[0] = _candles(305)
    class CorruptTrainer(CandidateTrainer):
        def train(self, *args):
            result = super().train(*args)
            result.artifact_path.write_bytes(b"invalid")
            return result
    service.trainer_factory = CorruptTrainer
    with pytest.raises(ValueError, match="previous candidates were kept"):
        service.train_candidate(request)
    assert repos.model_registry.get(first["model_id"]) is not None
    assert len(list(tmp_path.glob("*.pkl"))) == 1


def test_registration_failure_rolls_back_replacement_and_cleans_new_artifact(repos, monkeypatch, tmp_path):
    service, request, data = setup(repos, monkeypatch, tmp_path)
    first = service.train_candidate(request)
    data[0] = _candles(305)
    monkeypatch.setattr(repos.session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("commit failed")))
    with pytest.raises(RuntimeError, match="commit failed"):
        service.train_candidate(request)
    assert repos.model_registry.get(first["model_id"]) is not None
    assert len(repos.model_registry.get_all()) == 1
    assert len(list(tmp_path.glob("*.pkl"))) == 1


def test_champion_and_retired_models_are_never_replaced(repos, monkeypatch, tmp_path):
    service, request, data = setup(repos, monkeypatch, tmp_path)
    first = service.train_candidate(request)
    repos.model_registry.promote_candidate(first["model_id"], "reviewer", "paper review")
    data[0] = _candles(305)
    second = service.train_candidate(request)
    assert second["replaced_model_ids"] == []
    repos.model_registry.promote_candidate(second["model_id"], "reviewer", "paper review")
    data[0] = _candles(310)
    third = service.train_candidate(request)
    assert third["replaced_model_ids"] == []
    assert repos.model_registry.get(first["model_id"]).status == "retired"
    assert repos.model_registry.get(second["model_id"]).status == "champion"


def test_manual_and_self_training_candidates_have_separate_families(repos, monkeypatch, tmp_path):
    service, request, data = setup(repos, monkeypatch, tmp_path)
    manual = service.train_candidate(request)
    data[0] = _candles(305)
    first_self = service.train_candidate(request, backfill=True)
    data[0] = _candles(310)
    second_self = service.train_candidate(request, backfill=True)
    assert second_self["replaced_model_ids"] == [first_self["model_id"]]
    assert repos.model_registry.get(manual["model_id"]) is not None
    assert len(repos.model_registry.get_all()) == 2


@pytest.mark.parametrize("changed", [{"data_source": "mt5"}, {"symbol": "EURUSD"}, {"max_depth": 4}, {"horizon_candles": 4}])
def test_different_sources_markets_or_settings_remain_separate(repos, monkeypatch, tmp_path, changed):
    service, request, data = setup(repos, monkeypatch, tmp_path)
    first = service.train_candidate(request)
    data[0] = _candles(305)
    second = service.train_candidate({**request, **changed})
    assert second["replaced_model_ids"] == []
    assert repos.model_registry.get(first["model_id"]) is not None
    assert len(repos.model_registry.get_all()) == 2


def test_artifacts_outside_managed_directory_are_kept(tmp_path):
    outside = tmp_path / "outside.pkl"
    outside.write_bytes(b"keep")
    service = ModelTrainingService(artifact_directory=tmp_path / "managed")
    warnings = service._remove_replaced_artifacts([{"model_id": "old", "artifact_path": str(outside)}])
    assert outside.read_bytes() == b"keep"
    assert warnings


@pytest.mark.parametrize("value", ["true", 1, None])
def test_replacement_setting_requires_a_boolean(value):
    with pytest.raises(ValueError, match="must be a boolean"):
        ModelTrainingService().validate_request({"replace_previous_candidate": value})
