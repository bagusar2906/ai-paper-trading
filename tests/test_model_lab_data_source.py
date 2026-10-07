import json
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.model_lab_data_source_service import ModelLabDataSourceService
from app.services.model_training_service import ModelTrainingService
from app.services.training_data_sync_service import TrainingDataSyncService
from tests.test_model_training_service import _candles


def test_lab_preference_persists_without_changing_trading_source(repos, monkeypatch):
    monkeypatch.setattr(repos, "close", lambda: None)
    repos.settings.set("market_data_provider", "mt5")
    service = ModelLabDataSourceService(lambda: repos)
    assert service.get() == {"data_source": "trading"}
    assert service.set("yahoo") == {"data_source": "yahoo"}
    assert ModelLabDataSourceService(lambda: repos).get()["data_source"] == "yahoo"
    assert repos.settings.get_market_data_provider() == "mt5"


@pytest.mark.parametrize("value", [None, 123, "invalid", "", "YAHOO"])
def test_invalid_source_rejected_before_connection_or_persistence(value):
    with pytest.raises(ValueError, match="data_source"):
        ModelTrainingService().validate_request({"data_source": value})
    service = ModelLabDataSourceService(lambda: pytest.fail("Invalid source must not write settings"))
    with pytest.raises(ValueError):
        service.set(value)


def test_lab_source_api_only_changes_lab_preference(monkeypatch):
    stored = {"market_data_provider": "oanda"}
    repos = SimpleNamespace(settings=SimpleNamespace(get=lambda key, default=None: stored.get(key, default),
                            set=lambda key, value: stored.update({key: value})), close=lambda: None)
    service = ModelLabDataSourceService(lambda: repos)
    monkeypatch.setattr("app.api.models.ModelLabDataSourceService", lambda: service)
    client = TestClient(app)
    assert client.get("/models/data-source").json()["data_source"] == "trading"
    assert client.put("/models/data-source", json={"data_source": "twelve_data"}).json()["data_source"] == "twelve_data"
    assert client.put("/models/data-source", json={"data_source": "bad"}).status_code == 400
    assert stored["market_data_provider"] == "oanda"


def test_self_training_keeps_selected_source_after_restart_and_rejects_invalid_source():
    from tests.test_self_training_scheduler import scheduler
    from app.scheduler.self_training_scheduler import SelfTrainingScheduler
    worker = scheduler(SimpleNamespace())
    worker.configure({"enabled": True, "training": {"data_source": "yahoo"}})
    reopened = SelfTrainingScheduler(worker.repository_factory)
    assert reopened.configuration()["training"]["data_source"] == "yahoo"
    with pytest.raises(ValueError):
        worker.configure({"enabled": True, "training": {"data_source": "bad"}})
    assert reopened.configuration()["training"]["data_source"] == "yahoo"


def test_source_selection_controls_downloads_backfill_and_training_identity(repos, monkeypatch, tmp_path):
    monkeypatch.setattr(repos, "close", lambda: None)
    candles = _candles(300)
    selected = []
    class Provider:
        def __init__(self, source):
            self.source_name = source
        def get_history(self, *args):
            return candles
        def get_history_range(self, symbol, timeframe, start, end):
            return candles[(candles.index >= start) & (candles.index < end)]
        def disconnect(self):
            pass
    def create(source=None):
        effective = source or repos.settings.get_market_data_provider()
        selected.append(effective)
        return Provider(effective)
    monkeypatch.setattr("app.services.model_training_service.TrainingDataSyncService",
                        lambda factory: TrainingDataSyncService(factory, now=lambda: candles.index[-1] + pd.Timedelta(minutes=5)))
    service = ModelTrainingService(create, lambda: repos, artifact_directory=tmp_path)
    request = {"bars": 300, "horizon_candles": 3, "n_estimators": 25,
               "feature_set_id": "raw-ohlcv-v1", "data_source": "yahoo"}
    repos.settings.set("market_data_provider", "mt5")
    first = service.train_candidate(request, backfill=True)
    repos.settings.set("market_data_provider", "oanda")
    duplicate = service.train_candidate(request, backfill=True)
    third = service.train_candidate({**request, "data_source": "trading"}, backfill=True)
    assert selected == ["yahoo", "yahoo", "oanda"]
    assert first["data_sync"]["source"] == "yahoo"
    assert duplicate["status"] == "duplicate"
    assert third["status"] == "candidate"
    assert len(repos.market_candles.get_all()) == 600
    contexts = [json.loads(item.metadata_json)["market_context"] for item in repos.model_registry.get_all()]
    assert {item["data_source"] for item in contexts} == {"yahoo", "oanda"}
    from app.api.models import _market_context
    for context in contexts:
        assert _market_context(json.dumps({"market_context": context}))["data_source"] == context["data_source"]


def test_health_uses_the_champions_recorded_source(monkeypatch):
    from app.services.model_health_service import ModelHealthService
    champion = SimpleNamespace(model_id="champion", status="champion", feature_set_id="core-v1",
                               metadata_json=json.dumps({"market_context": {"symbol": "XAUUSD", "timeframe": "M5", "data_source": "yahoo"},
                                                         "feature_baseline": {"Close": {"median": 1, "iqr": 1}}}))
    repos = SimpleNamespace(model_registry=SimpleNamespace(get_all=lambda: [champion]), close=lambda: None)
    selected = []
    def create(source):
        selected.append(source)
        return SimpleNamespace(get_history=lambda *args: pd.DataFrame({"Close": [1] * 100}), disconnect=lambda: None)
    monkeypatch.setattr("app.services.model_health_service.build_core_v1_features", lambda frame: frame)
    assert ModelHealthService(create, lambda: repos).check()["status"] == "healthy"
    assert selected == ["yahoo"]
