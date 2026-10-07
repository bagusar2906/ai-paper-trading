import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scheduler.self_training_scheduler import SelfTrainingScheduler
from app.services.model_training_service import ModelTrainingService
from tests.test_ml_candidate_training import _candles


def scheduler(trainer):
    store = {}
    settings = SimpleNamespace(get=lambda key, default=None: store.get(key, default), set=lambda key, value: store.update({key: value}))
    return SelfTrainingScheduler(lambda: SimpleNamespace(settings=settings, close=lambda: None), lambda: trainer)


def test_disabled_scheduler_never_fetches_or_trains_and_enable_settings_persist():
    worker = scheduler(SimpleNamespace(train_candidate=lambda _, **kwargs: pytest.fail("disabled must not train")))
    assert worker.run_once()["status"] == "disabled"
    worker.configure({"enabled": True, "interval_minutes": 15, "training": {"bars": 300}})
    assert worker.configuration()["training"]["feature_set_id"] == "raw-ohlcv-v1"
    restarted = SelfTrainingScheduler(worker.repository_factory)
    assert restarted.configuration()["enabled"] is True
    worker.configure({"enabled": False})
    assert worker.run_once()["status"] == "disabled"


def test_unchanged_data_failures_and_recovery_are_reported():
    outcomes = iter([{"status": "duplicate", "model_id": "existing"}, RuntimeError("No completed candles available"), {"status": "candidate", "model_id": "new"}])
    def train(parameters, *, backfill=False):
        assert backfill is True
        assert parameters["feature_set_id"] == "raw-ohlcv-v1"
        result = next(outcomes)
        if isinstance(result, Exception):
            raise result
        return result
    worker = scheduler(SimpleNamespace(train_candidate=train))
    worker.configure({"enabled": True})
    assert worker.run_once()["status"] == "skipped_unchanged"
    assert worker.run_once()["status"] == "failed"
    assert "completed candles" in worker.status()["last_run"]["message"]
    report = worker.run_once()
    assert report["status"] == "candidate_created"
    assert report["model_id"] == "new"
    assert "next_check_at" in report
    assert worker.status()["automatic_promotion"] is False


def test_self_training_is_single_flight_and_stops_with_backend():
    started, finish = threading.Event(), threading.Event()
    def train(_, *, backfill=False):
        assert backfill is True
        started.set()
        assert finish.wait(3)
        return {"status": "candidate", "model_id": "a"}
    worker = scheduler(SimpleNamespace(train_candidate=train))
    worker.configure({"enabled": True})
    worker.start()
    try:
        assert started.wait(3)
        assert worker.status()["running"]
        assert worker.run_once()["status"] == "busy"
        worker.configure({"enabled": False})
        finish.set()
    finally:
        finish.set()
        worker.stop()
    assert not worker._thread.is_alive()
    assert worker.configuration()["enabled"] is False


@pytest.mark.parametrize("settings_request", [{"enabled": "true"}, {"enabled": True, "interval_minutes": 1}, {"enabled": True, "interval_minutes": 5.5}, {"enabled": True, "training": {"feature_set_id": "unknown"}}, {"enabled": True, "training": {"bars": 10}}])
def test_invalid_self_training_settings_are_rejected_without_data_access(settings_request):
    worker = scheduler(SimpleNamespace(train_candidate=lambda _, **kwargs: pytest.fail("must not train")))
    with pytest.raises(ValueError):
        worker.configure(settings_request)
    assert worker.configuration()["enabled"] is False


def test_training_lock_prevents_manual_and_background_overlap_and_releases_after_error():
    service = ModelTrainingService()
    service._training_lock.acquire()
    try:
        with pytest.raises(RuntimeError, match="already in progress"):
            service.train_candidate({})
    finally:
        service._training_lock.release()
    with pytest.raises(ValueError):
        service.train_candidate({"bars": 1})
    assert not service._training_lock.locked()


def test_self_training_api_reads_updates_and_rejects_invalid_settings(monkeypatch):
    worker = scheduler(SimpleNamespace())
    monkeypatch.setattr("app.api.models.self_training_scheduler", worker)
    client = TestClient(app)
    assert client.get("/models/self-training").json()["configuration"]["enabled"] is False
    assert client.put("/models/self-training", json={"enabled": True, "interval_minutes": 15}).status_code == 200
    assert client.put("/models/self-training", json={"enabled": True, "interval_minutes": 1}).status_code == 400
    assert client.put("/models/self-training", json={"enabled": False}).json()["configuration"]["enabled"] is False


def test_self_training_downloads_raw_data_and_only_retrains_changed_inputs(tmp_path, repos, monkeypatch):
    data = [_candles(300)]
    fetched = []
    class Provider:
        source_name = "test"
        def get_history(self, symbol, timeframe, bars):
            fetched.append((symbol, timeframe, bars))
            return data[0]
        def get_history_range(self, symbol, timeframe, start, end):
            return data[0][(data[0].index >= start) & (data[0].index < end)]
        def disconnect(self):
            pass
    from app.services.training_data_sync_service import TrainingDataSyncService
    import pandas as pd
    monkeypatch.setattr("app.services.model_training_service.TrainingDataSyncService", lambda factory: TrainingDataSyncService(factory, now=lambda: data[0].index.max() + pd.Timedelta(minutes=5)))
    monkeypatch.setattr(repos, "close", lambda: None)
    service = ModelTrainingService(provider_factory=Provider, repository_factory=lambda: repos, artifact_directory=tmp_path)
    worker = scheduler(service)
    worker.configure({"enabled": True, "training": {"feature_set_id": "raw-ohlcv-v1", "bars": 300, "horizon_candles": 3, "up_return_threshold": .0001, "n_estimators": 25}})
    first = worker.run_once()
    assert first["status"] == "candidate_created"
    assert worker.run_once()["status"] == "skipped_unchanged"
    data[0] = _candles(305)
    third = worker.run_once()
    assert third["status"] == "candidate_created"
    assert third["model_id"] != first["model_id"]
    assert len(fetched) == 1
    assert third["data_sync"]["downloaded_bars"] == 5
    assert len(repos.market_candles.get_all()) == 305
    assert len(repos.model_registry.get_all()) == 2
    assert all(model.status == "candidate" and model.feature_set_id == "raw-ohlcv-v1" for model in repos.model_registry.get_all())


def test_backend_lifespan_starts_and_stops_self_training(monkeypatch):
    import asyncio
    import importlib
    main = importlib.import_module("app.main")
    calls = []
    for name in ("configure_logging", "init_database", "initialize_database"):
        monkeypatch.setattr(main, name, lambda: None)
    for name in ("scheduler", "model_monitoring_scheduler"):
        monkeypatch.setattr(main, name, SimpleNamespace(start=lambda: None, stop=lambda: None))
    monkeypatch.setattr(main, "self_training_scheduler", SimpleNamespace(start=lambda: calls.append("start"), stop=lambda: calls.append("stop")))
    async def run():
        async with main.lifespan(main.app):
            assert calls == ["start"]
    asyncio.run(run())
    assert calls == ["start", "stop"]


def test_reopened_scheduler_catches_up_immediately_and_keeps_sync_status():
    worker = scheduler(SimpleNamespace())
    worker.configure({"enabled": True, "interval_minutes": 1440})
    worker._write(worker.STATUS_KEY, {"status": "running", "started_at": "2026-01-01T00:00:00Z"})
    called = threading.Event()
    def train(request, *, backfill=False):
        assert backfill is True
        called.set()
        return {"status": "duplicate", "model_id": "existing", "data_sync": {"downloaded_bars": 5}}
    reopened = SelfTrainingScheduler(worker.repository_factory, lambda: SimpleNamespace(train_candidate=train))
    assert reopened.status()["last_run"]["status"] == "interrupted"
    reopened.start()
    try:
        assert called.wait(3)
    finally:
        reopened.stop()
    assert reopened.status()["last_run"]["status"] == "skipped_unchanged"
    assert reopened.status()["last_run"]["data_sync"]["downloaded_bars"] == 5
