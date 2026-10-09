from dataclasses import asdict

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.brokers.paper_broker import PaperBroker
from app.database.base import Base
from app.engine.trading_engine import TradingEngine
from app.enums.signal_action import SignalAction
from app.factories.repository_factory import RepositoryFactory
from app.models.signal import TradingSignal
from app.services.trading_recovery_service import TradingRecoveryService


class Provider:
    source_name = "recovery-test"

    def __init__(self, frame):
        self.frame = frame
        self.calls = []
        self.fail_on = None

    def get_history(self, symbol, timeframe, bars):
        return self.frame.tail(bars)

    def get_history_range(self, symbol, timeframe, start, end):
        self.calls.append((start, end))
        if len(self.calls) == self.fail_on:
            raise RuntimeError("download interrupted")
        return self.frame[(self.frame.index >= start) & (self.frame.index < end)]


class Strategy:
    def __init__(self):
        self.seen = []

    def can_run(self, frame):
        return len(frame) >= 3

    def prepare(self, frame):
        return frame

    def generate_signal(self, symbol, frame):
        self.seen.append(frame.index[-1])
        price = float(frame.Close.iloc[-1])
        return TradingSignal(symbol, SignalAction.BUY, price, frame.index[-1].to_pydatetime(),
                             stop_loss=price - 10, take_profit=price + 2)


def candles(n):
    prices = [2000.0 + i for i in range(n)]
    return pd.DataFrame({"Open": prices, "High": [p + 1 for p in prices],
                         "Low": [p - 1 for p in prices], "Close": prices,
                         "Volume": [10.0] * n},
                        index=pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC"))


@pytest.fixture
def factory(tmp_path):
    db = create_engine(f"sqlite:///{tmp_path / 'paper.db'}")
    Base.metadata.create_all(db)
    sessions = sessionmaker(bind=db, autoflush=False)
    yield lambda: RepositoryFactory(session_factory=sessions)
    db.dispose()


def engine_for(factory, provider, mode=None):
    repos = factory()
    if mode:
        repos.settings.set("trading_mode", mode)
    broker = PaperBroker(repos=repos)
    return TradingEngine(provider, Strategy(), broker, "XAUUSD", "M5", bars=5)


def run(engine, now=None):
    service = TradingRecoveryService(engine, now=lambda: now or engine.provider.frame.index[-1] + pd.Timedelta(minutes=5))
    service.PAGE_BARS = 3
    return service.run()


def close(engine):
    engine.broker.repos.close()


def checkpoint(engine):
    return engine.broker.repos.trading_checkpoints.get("recovery-test", "XAUUSD", "M5")


def snapshot(engine):
    broker = engine.broker
    return {"account": asdict(broker.get_account()),
            "positions": [(p.entry_price, p.quantity, p.opened_at) for p in broker.get_positions()],
            "trades": [(t.entry_price, t.exit_price, t.pnl, t.opened_at, t.closed_at) for t in broker.get_trades()],
            "signals": [(s.signal_time, s.action, s.price) for s in broker.repos.signals.get_all()],
            "checkpoint": checkpoint(engine).candle_time}


def test_restart_replays_downtime_beyond_history_window_exactly_once(factory):
    provider = Provider(candles(5))
    first = engine_for(factory, provider, "AUTO")
    run(first)
    assert len(first.broker.get_positions()) == 1
    close(first)
    provider.frame = candles(22)
    restarted = engine_for(factory, provider)
    result = run(restarted)
    assert "17 new candle(s)" in result.message
    assert restarted.strategy.seen == list(provider.frame.index[5:])
    assert len(restarted.broker.get_trades()) == 8
    assert restarted.broker.get_trades()[0].closed_at == provider.frame.index[6].tz_localize(None).to_pydatetime()
    saved = snapshot(restarted)
    assert run(restarted).message == "No new completed candles"
    assert snapshot(restarted) == saved
    close(restarted)
    reopened = engine_for(factory, provider)
    assert reopened.broker.get_trading_mode() == "AUTO"
    assert run(reopened).message == "No new completed candles"
    assert snapshot(reopened) == saved
    close(reopened)


def test_restart_matches_uninterrupted_simulation(factory, tmp_path):
    provider = Provider(candles(5))
    first = engine_for(factory, provider, "AUTO")
    run(first)
    close(first)
    provider.frame = candles(14)
    recovered = engine_for(factory, provider)
    run(recovered)
    expected = snapshot(recovered)
    close(recovered)
    db = create_engine(f"sqlite:///{tmp_path / 'continuous.db'}")
    Base.metadata.create_all(db)
    other_factory = lambda: RepositoryFactory(session_factory=sessionmaker(bind=db, autoflush=False))
    continuous_provider = Provider(candles(5))
    continuous = engine_for(other_factory, continuous_provider, "AUTO")
    run(continuous)
    for n in range(6, 15):
        continuous_provider.frame = candles(n)
        run(continuous)
    assert snapshot(continuous) == expected
    close(continuous)
    db.dispose()


def test_interrupted_candle_rolls_back_trades_and_checkpoint(factory, monkeypatch):
    provider = Provider(candles(5))
    engine = engine_for(factory, provider, "AUTO")
    run(engine)
    provider.frame = candles(6)
    run(engine)
    before = snapshot(engine)
    provider.frame = candles(7)  # closes an existing position and opens another
    repository = engine.broker.repos.trading_checkpoints
    original = repository.save
    def interrupted(*args):
        original(*args)
        raise RuntimeError("power loss")
    monkeypatch.setattr(repository, "save", interrupted)
    with pytest.raises(RuntimeError, match="power loss"):
        run(engine)
    assert snapshot(engine) == before
    close(engine)
    restarted = engine_for(factory, provider)
    run(restarted)
    assert len(restarted.broker.get_trades()) == 1
    assert len(restarted.broker.repos.signals.get_all()) == 3
    assert checkpoint(restarted).candle_time == provider.frame.index[-1].tz_localize(None).to_pydatetime()
    close(restarted)


def test_download_failure_keeps_committed_candles_for_next_restart(factory):
    provider = Provider(candles(5))
    engine = engine_for(factory, provider, "AUTO")
    run(engine)
    provider.frame = candles(15)
    provider.calls.clear()
    provider.fail_on = 2
    with pytest.raises(RuntimeError, match="download interrupted"):
        run(engine)
    assert checkpoint(engine).candle_time == provider.frame.index[6].tz_localize(None).to_pydatetime()
    close(engine)
    provider.calls.clear()
    provider.fail_on = None
    restarted = engine_for(factory, provider)
    run(restarted)
    assert restarted.strategy.seen == list(provider.frame.index[7:])
    assert len(restarted.broker.repos.signals.get_all()) == 11
    close(restarted)


def test_missing_anchor_does_not_skip_forward(factory):
    provider = Provider(candles(5))
    engine = engine_for(factory, provider, "AUTO")
    run(engine)
    before = snapshot(engine)
    provider.frame = candles(20).tail(5)
    with pytest.raises(RuntimeError, match="Resume point preserved"):
        run(engine)
    assert snapshot(engine) == before
    close(engine)


def test_manual_mode_skips_historical_entries_and_survives_restart(factory):
    provider = Provider(candles(5))
    engine = engine_for(factory, provider, "MANUAL")
    run(engine)
    close(engine)
    provider.frame = candles(15)
    reopened = engine_for(factory, provider)
    run(reopened)
    assert reopened.strategy.seen == [provider.frame.index[-1]]
    assert reopened.broker.get_positions() == []
    assert reopened.broker.get_trading_mode() == "MANUAL"
    assert provider.calls == []
    close(reopened)


def test_forming_candle_and_unchanged_history_are_not_executed(factory):
    provider = Provider(candles(5))
    engine = engine_for(factory, provider, "AUTO")
    now = provider.frame.index[-1] + pd.Timedelta(minutes=2)
    run(engine, now)
    assert engine.strategy.seen == [provider.frame.index[-2]]
    provider.frame = candles(6)
    run(engine, provider.frame.index[-1] + pd.Timedelta(minutes=2))
    assert engine.strategy.seen[-1] == provider.frame.index[-2]
    assert len(engine.strategy.seen) == 2
    close(engine)


def test_invalid_download_preserves_checkpoint(factory):
    provider = Provider(candles(5))
    engine = engine_for(factory, provider, "AUTO")
    run(engine)
    before = snapshot(engine)
    provider.frame = candles(7)
    provider.frame.iloc[-1, provider.frame.columns.get_loc("Close")] = float("nan")
    with pytest.raises(RuntimeError, match="invalid prices"):
        run(engine)
    assert snapshot(engine) == before
    close(engine)


def test_production_engine_uses_recovery_but_backtests_do_not(factory, monkeypatch):
    provider = Provider(candles(5))
    engine = engine_for(factory, provider, "AUTO")
    monkeypatch.setattr("app.services.trading_recovery_service.TradingRecoveryService.run", lambda self: "recovered")
    engine.resume_pending = True
    assert engine.run_once() == "recovered"
    engine.resume_pending = False
    assert engine.run_once().message == "Completed"
    assert checkpoint(engine) is None
    close(engine)


def test_abrupt_process_exit_does_not_commit_half_a_candle(factory):
    import subprocess
    import sys

    provider = Provider(candles(6))
    engine = engine_for(factory, Provider(candles(5)), "AUTO")
    run(engine)
    engine.provider = provider
    run(engine)
    before = snapshot(engine)
    url = str(engine.broker.repos.session.get_bind().url)
    close(engine)
    code = f'''import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.factories.repository_factory import RepositoryFactory
from tests.test_trading_recovery import Provider, candles, engine_for, run
db = create_engine({url!r})
factory = lambda: RepositoryFactory(session_factory=sessionmaker(bind=db, autoflush=False))
engine = engine_for(factory, Provider(candles(7)))
repository = engine.broker.repos.trading_checkpoints
original = repository.save
def power_loss(*args):
    original(*args)
    os._exit(9)
repository.save = power_loss
run(engine)
'''
    process = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=20)
    assert process.returncode == 9, process.stderr.decode()
    restarted = engine_for(factory, Provider(candles(7)))
    assert snapshot(restarted) == before
    run(restarted)
    assert len(restarted.broker.get_trades()) == 1
    assert len(restarted.broker.repos.signals.get_all()) == 3
    close(restarted)


def test_another_worker_cannot_repeat_a_committed_candle(factory):
    provider = Provider(candles(5))
    first = engine_for(factory, provider, "AUTO")
    second = engine_for(factory, provider)
    first_service = TradingRecoveryService(first)
    second_service = TradingRecoveryService(second)
    first_service._process(provider.frame)
    before = snapshot(first)
    assert second_service._process(provider.frame) is None
    assert snapshot(second) == before
    close(first)
    close(second)
