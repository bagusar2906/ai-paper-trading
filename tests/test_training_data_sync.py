from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.factories.repository_factory import RepositoryFactory
from app.services.training_data_sync_service import TrainingDataSyncService
from tests.test_model_training_service import _candles


class Provider:
    source_name = "test-source"

    def __init__(self, frame):
        self.frame = frame
        self.history_calls = []
        self.range_calls = []
        self.fail_on = None

    def get_history(self, symbol, timeframe, bars):
        self.history_calls.append((symbol, timeframe, bars))
        return self.frame.tail(bars)

    def get_history_range(self, symbol, timeframe, start, end):
        self.range_calls.append((start, end))
        if len(self.range_calls) == self.fail_on:
            raise RuntimeError("connection lost")
        return self.frame[(self.frame.index >= start) & (self.frame.index < end)]


def test_restart_resumes_persisted_history_and_keeps_all_downtime_data(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'history.db'}")
    Base.metadata.create_all(engine)
    factory = lambda: RepositoryFactory(session_factory=sessionmaker(bind=engine))
    data = _candles(8)
    provider = Provider(data)
    first = TrainingDataSyncService(factory, now=lambda: data.index[-1] + pd.Timedelta(minutes=5))
    first.synchronize(provider, "XAUUSD", "M5", 8)
    # A new service and DB session simulate reopening the app. Downtime exceeds
    # the eight-candle training window and requires several bounded pages.
    provider.frame = _candles(25)
    provider.range_calls.clear()
    restarted = TrainingDataSyncService(factory, now=lambda: provider.frame.index[-1] + pd.Timedelta(minutes=5))
    restarted.PAGE_BARS = 3
    frame, report = restarted.synchronize(provider, "XAUUSD", "M5", 8)
    assert len(provider.history_calls) == 1
    assert provider.range_calls[0][0] == data.index[-1]
    assert report["downloaded_bars"] == 17
    assert frame.index.equals(provider.frame.tail(8).index)
    repos = factory()
    try:
        assert len(repos.market_candles.get_all()) == 25
    finally:
        repos.close()
        engine.dispose()


def test_interrupted_download_retries_from_last_committed_page(repos, monkeypatch):
    monkeypatch.setattr(repos, "close", lambda: None)
    provider = Provider(_candles(8))
    worker = TrainingDataSyncService(lambda: repos, now=lambda: provider.frame.index[-1] + pd.Timedelta(minutes=5))
    worker.PAGE_BARS = 3
    worker.synchronize(provider, "XAUUSD", "M5", 8)
    provider.frame = _candles(20)
    provider.range_calls.clear()
    provider.fail_on = 2
    with pytest.raises(RuntimeError, match="connection lost"):
        worker.synchronize(provider, "XAUUSD", "M5", 8)
    last = repos.market_candles.latest_time(provider.source_name, "XAUUSD", "M5")
    assert pd.Timestamp(last) == provider.frame.index[9]
    provider.range_calls.clear()
    provider.fail_on = None
    restarted = TrainingDataSyncService(lambda: repos, now=worker.now)
    restarted.PAGE_BARS = 3
    _, report = restarted.synchronize(provider, "XAUUSD", "M5", 8)
    assert provider.range_calls[0][0] == pd.Timestamp(last)
    assert report["downloaded_bars"] == 10
    assert len(repos.market_candles.get_all()) == 20


def test_unchanged_data_deduplicates_and_forming_candle_is_excluded(repos, monkeypatch):
    monkeypatch.setattr(repos, "close", lambda: None)
    provider = Provider(_candles(10))
    now = provider.frame.index[-1] + pd.Timedelta(minutes=2)
    sync = TrainingDataSyncService(lambda: repos, now=lambda: now)
    frame, report = sync.synchronize(provider, "XAUUSD", "M5", 10)
    assert len(frame) == 9
    assert report["last_candle_at"] == provider.frame.index[-2].isoformat()
    _, report = sync.synchronize(provider, "XAUUSD", "M5", 10)
    assert report["downloaded_bars"] == 0
    assert len(repos.market_candles.get_all()) == 9


def test_market_and_source_changes_have_separate_resume_points(repos, monkeypatch):
    monkeypatch.setattr(repos, "close", lambda: None)
    provider = Provider(_candles(8))
    sync = TrainingDataSyncService(lambda: repos, now=lambda: provider.frame.index[-1] + pd.Timedelta(minutes=5))
    sync.synchronize(provider, "XAUUSD", "M5", 8)
    _, report = sync.synchronize(provider, "EURUSD", "M5", 8)
    assert report["resumed_from"] is None
    provider.source_name = "another-source"
    _, report = sync.synchronize(provider, "XAUUSD", "M5", 8)
    assert report["resumed_from"] is None
    assert len(repos.market_candles.get_all()) == 24


def test_unavailable_overlap_does_not_skip_missing_history(repos, monkeypatch):
    monkeypatch.setattr(repos, "close", lambda: None)
    provider = Provider(_candles(8))
    sync = TrainingDataSyncService(lambda: repos, now=lambda: provider.frame.index[-1] + pd.Timedelta(minutes=5))
    sync.synchronize(provider, "XAUUSD", "M5", 8)
    last = repos.market_candles.latest_time(provider.source_name, "XAUUSD", "M5")
    provider.frame = _candles(25).tail(5)
    with pytest.raises(RuntimeError, match="Resume point preserved"):
        sync.synchronize(provider, "XAUUSD", "M5", 8)
    assert repos.market_candles.latest_time(provider.source_name, "XAUUSD", "M5") == last
    assert len(repos.market_candles.get_all()) == 8


def test_nonfinite_download_does_not_move_resume_point(repos, monkeypatch):
    monkeypatch.setattr(repos, "close", lambda: None)
    provider = Provider(_candles(8))
    sync = TrainingDataSyncService(lambda: repos, now=lambda: provider.frame.index[-1] + pd.Timedelta(minutes=5))
    sync.synchronize(provider, "XAUUSD", "M5", 8)
    last = repos.market_candles.latest_time(provider.source_name, "XAUUSD", "M5")
    provider.frame = _candles(12)
    provider.frame.iloc[-1, provider.frame.columns.get_loc("Close")] = float("nan")
    with pytest.raises(RuntimeError, match="invalid prices"):
        sync.synchronize(provider, "XAUUSD", "M5", 8)
    assert repos.market_candles.latest_time(provider.source_name, "XAUUSD", "M5") == last


def test_empty_closed_market_pages_do_not_fabricate_candles(repos, monkeypatch):
    monkeypatch.setattr(repos, "close", lambda: None)
    provider = Provider(_candles(8))
    sync = TrainingDataSyncService(lambda: repos, now=lambda: provider.frame.index[-1] + pd.Timedelta(minutes=40))
    sync.PAGE_BARS = 3
    _, report = sync.synchronize(provider, "XAUUSD", "M5", 8)
    assert report["downloaded_bars"] == 8
    assert report["pages"] > 2
    assert len(repos.market_candles.get_all()) == 8


def test_naive_provider_timestamps_are_normalized_to_utc(repos, monkeypatch):
    monkeypatch.setattr(repos, "close", lambda: None)
    provider = Provider(_candles(8))
    aware = provider.frame.index.copy()
    provider.frame.index = provider.frame.index.tz_localize(None)
    provider.get_history_range = lambda symbol, timeframe, start, end: provider.frame
    sync = TrainingDataSyncService(lambda: repos, now=lambda: aware[-1] + pd.Timedelta(minutes=5))
    frame, _ = sync.synchronize(provider, "XAUUSD", "M5", 8)
    assert str(frame.index.tz) == "UTC"
    assert frame.index.equals(aware)


def test_oanda_range_uses_dates_without_count_and_only_complete_candles(monkeypatch):
    from app.providers.oanda_provider import OandaProvider
    sent = {}
    start, end = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-01-02", tz="UTC")
    candle = {"time": start.isoformat(), "complete": True, "mid": {"o": "1", "h": "2", "l": "1", "c": "2"}}
    def get(url, **kwargs):
        sent.update(kwargs["params"])
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"candles": [candle, {**candle, "complete": False}]})
    monkeypatch.setattr("app.providers.oanda_provider.requests.get", get)
    frame = OandaProvider("key").get_history_range("XAUUSD", "M5", start, end)
    assert sent["from"] == start.isoformat() and sent["to"] == end.isoformat()
    assert "count" not in sent
    assert len(frame) == 1


def test_twelve_data_range_requests_full_page_with_utc_bounds(monkeypatch):
    from app.providers.twelve_data_provider import TwelveDataProvider
    provider = TwelveDataProvider("key")
    provider.connect()
    sent = {}
    def get(endpoint, params):
        sent.update(params)
        return {"values": [{"datetime": "2026-01-01 00:00:00", "open": "1", "high": "2", "low": "1", "close": "2"}]}
    monkeypatch.setattr(provider, "_get", get)
    start, end = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-01-02", tz="UTC")
    frame = provider.get_history_range("XAUUSD", "M5", start, end)
    assert sent["outputsize"] == 5000 and sent["timezone"] == "UTC"
    assert sent["start_date"] == "2026-01-01 00:00:00"
    assert frame["Volume"].iloc[0] == 0


def test_mt5_range_uses_utc_and_excludes_end_boundary(monkeypatch):
    from app.providers.mt5_provider import MT5Provider
    start, end = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-01-01 00:05", tz="UTC")
    sent = []
    def copy(symbol, timeframe, date_from, date_to):
        sent.extend([date_from, date_to])
        return [{"time": int(stamp.timestamp()), "open": 1, "high": 2, "low": 1, "close": 2, "tick_volume": 10} for stamp in (start, end)]
    monkeypatch.setattr("app.providers.mt5_provider.mt5", SimpleNamespace(TIMEFRAME_M5=5, copy_rates_range=copy))
    provider = MT5Provider()
    provider._connected = True
    frame = provider.get_history_range("XAUUSD", "M5", start, end)
    assert len(frame) == 1
    assert sent == [start.to_pydatetime(), end.to_pydatetime()]


def test_yahoo_range_uses_dates_and_exposes_retention_errors(monkeypatch):
    from app.providers.yahoo_provider import YahooProvider
    sent = {}
    def history(**kwargs):
        sent.update(kwargs)
        raise RuntimeError("requested range unavailable")
    monkeypatch.setattr("app.providers.yahoo_provider.yf.Ticker", lambda _: SimpleNamespace(history=history))
    start, end = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-01-02", tz="UTC")
    with pytest.raises(RuntimeError, match="unavailable"):
        YahooProvider().get_history_range("XAUUSD", "M5", start, end)
    assert sent["raise_errors"] is True
    assert "period" not in sent


def test_training_failure_keeps_downloads_for_next_attempt(repos, monkeypatch, tmp_path):
    from app.services.model_training_service import ModelTrainingService
    monkeypatch.setattr(repos, "close", lambda: None)
    provider = Provider(_candles(300))
    provider.disconnect = lambda: None
    monkeypatch.setattr("app.services.model_training_service.TrainingDataSyncService",
                        lambda factory: TrainingDataSyncService(factory, now=lambda: provider.frame.index[-1] + pd.Timedelta(minutes=5)))
    class FailingTrainer:
        def __init__(self, *args, **kwargs):
            pass
        def train(self, *args):
            raise RuntimeError("training failed")
    service = ModelTrainingService(provider_factory=lambda: provider, repository_factory=lambda: repos,
                                   trainer_factory=FailingTrainer, artifact_directory=tmp_path)
    request = {"bars": 300, "feature_set_id": "raw-ohlcv-v1", "horizon_candles": 3}
    for _ in range(2):
        with pytest.raises(RuntimeError, match="training failed"):
            service.train_candidate(request, backfill=True)
    assert len(provider.history_calls) == 1
    assert len(repos.market_candles.get_all()) == 300
    assert repos.model_registry.get_all() == []


def test_bootstrap_respects_provider_maximum_page_size(repos, monkeypatch):
    monkeypatch.setattr(repos, "close", lambda: None)
    provider = Provider(_candles(8))
    sync = TrainingDataSyncService(lambda: repos, now=lambda: provider.frame.index[-1] + pd.Timedelta(minutes=5))
    sync.synchronize(provider, "XAUUSD", "M5", 5000)
    assert provider.history_calls[0][2] == 5000
