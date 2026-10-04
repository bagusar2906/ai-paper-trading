import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services.model_training_service import ModelTrainingService


def _candles(count=300):
    index = pd.date_range("2026-01-01", periods=count, freq="5min", tz="UTC")
    close = 2000 + np.sin(np.arange(count) / 2) * 8 + np.arange(count) * 0.01
    open_ = close + np.cos(np.arange(count)) * 0.15
    return pd.DataFrame({
        "Open": open_,
        "High": np.maximum(open_, close) + 0.5,
        "Low": np.minimum(open_, close) - 0.5,
        "Close": close,
        "Volume": 100 + np.arange(count),
    }, index=index)


def test_manual_training_registers_a_candidate_and_disconnects_provider(tmp_path):
    class Provider:
        disconnected = False

        def get_history(self, symbol, timeframe, bars):
            assert (symbol, timeframe, bars) == ("XAUUSD", "M5", 300)
            return _candles()

        def disconnect(self):
            self.disconnected = True

    provider = Provider()
    recorded = []

    class Trainer:
        def __init__(self, artifact_directory):
            assert artifact_directory == tmp_path

        def train(self, dataset, label_column, config):
            assert label_column == "future_return_up"
            assert config.walk_forward.purge_candles == 3
            return SimpleNamespace(
                model_id="candidate-xgb-test",
                training_run_id="train-test",
                metrics={"precision": 0.5},
            )

    class RegisteredCandidate:
        def __init__(self, repositories):
            self.repositories = repositories

        @property
        def model_id(self):
            assert not self.repositories.closed
            return "candidate-xgb-test"

        @property
        def status(self):
            assert not self.repositories.closed
            return "candidate"

    class Registry:
        def record_candidate(self, result):
            recorded.append(result.model_id)
            return RegisteredCandidate(repos)

    class Repositories:
        model_registry = Registry()
        closed = False

        def close(self):
            self.closed = True

    repos = Repositories()
    service = ModelTrainingService(
        provider_factory=lambda: provider,
        repository_factory=lambda: repos,
        trainer_factory=Trainer,
        artifact_directory=tmp_path,
    )

    response = service.train_candidate({
        "bars": 300,
        "horizon_candles": 3,
        "up_return_threshold": 0.0001,
    })

    assert response["status"] == "candidate"
    assert response["model_id"] == "candidate-xgb-test"
    assert response["training_rows"] > 0
    assert recorded == ["candidate-xgb-test"]
    assert provider.disconnected is True
    assert repos.closed is True


def test_manual_training_rejects_insufficient_history():
    service = ModelTrainingService()

    try:
        service.train_candidate({"bars": 249})
    except ValueError as error:
        assert "bars must be between" in str(error)
    else:
        raise AssertionError("expected invalid history size to be rejected")


def test_train_endpoint_returns_a_candidate_summary(monkeypatch):
    expected = {
        "model_id": "candidate-xgb-test",
        "training_run_id": "train-test",
        "status": "candidate",
        "training_rows": 250,
    }

    class Service:
        def train_candidate(self, request):
            assert request["bars"] == 300
            return expected

    monkeypatch.setattr("app.api.models.ModelTrainingService", lambda: Service())

    response = TestClient(app).post("/models/train", json={"bars": 300})

    assert response.status_code == 200
    assert response.json() == expected


def test_train_endpoint_exposes_provider_failures(monkeypatch):
    class Service:
        def train_candidate(self, request):
            raise RuntimeError("Yahoo Finance request failed for GC=F (M5): cache unavailable")

    monkeypatch.setattr("app.api.models.ModelTrainingService", lambda: Service())

    response = TestClient(app).post("/models/train", json={"bars": 300})

    assert response.status_code == 400
    assert "Yahoo Finance request failed" in response.json()["detail"]


def test_delete_model_endpoint_requires_audited_non_champion_deletion(monkeypatch):
    deleted = []
    registry = SimpleNamespace(
        delete_model=lambda model_id, reviewer, rationale: (
            deleted.append((model_id, reviewer, rationale))
            or "outside-managed-artifacts/model.pkl"
        )
    )
    repos = SimpleNamespace(model_registry=registry, close=lambda: None)
    monkeypatch.setattr("app.api.models.RepositoryFactory", lambda: repos)

    response = TestClient(app).request(
        "DELETE",
        "/models/candidate-xgb-test",
        json={"reviewer": "reviewer", "rationale": "obsolete candidate"},
    )

    assert response.status_code == 200
    assert response.json() == {"model_id": "candidate-xgb-test", "deleted": True}
    assert deleted == [("candidate-xgb-test", "reviewer", "obsolete candidate")]


def test_model_list_exposes_saved_validation_metrics(monkeypatch):
    registry = SimpleNamespace(get_all=lambda: [SimpleNamespace(
        model_id="candidate-xgb-test",
        status="candidate",
        feature_set_id="core-v1",
        label_definition_id="future-return-up",
        created_at="2026-10-04T00:00:00Z",
        metrics_json=json.dumps({"precision": 0.7, "brier_score": 0.2}),
    )])
    repos = SimpleNamespace(model_registry=registry, close=lambda: None)
    monkeypatch.setattr("app.api.models.RepositoryFactory", lambda: repos)

    response = TestClient(app).get("/models")

    assert response.status_code == 200
    assert response.json()[0]["metrics"] == {
        "precision": 0.7,
        "brier_score": 0.2,
    }
