from datetime import datetime

from app.enums.signal_action import SignalAction
from app.models.signal import TradingSignal


def _signal(action, timestamp):
    return TradingSignal(
        symbol="XAUUSD",
        action=action,
        price=2000.0,
        time=timestamp,
        confidence=0.75,
        reason="test",
    )


def test_upsert_keeps_one_signal_per_symbol_and_candle(repos):
    timestamp = datetime(2026, 10, 2, 16, 45)

    repos.signals.upsert_for_candle(_signal(SignalAction.HOLD, timestamp))
    repos.signals.upsert_for_candle(_signal(SignalAction.SELL, timestamp))

    signals = repos.signals.get_recent()
    assert len(signals) == 1
    assert signals[0].action == SignalAction.SELL


def test_recent_history_hides_legacy_duplicate_candle_rows(repos):
    timestamp = datetime(2026, 10, 2, 16, 45)

    repos.signals.add(_signal(SignalAction.HOLD, timestamp))
    repos.signals.add(_signal(SignalAction.SELL, timestamp))

    signals = repos.signals.get_recent()
    assert len(signals) == 1
    assert signals[0].action == SignalAction.SELL
