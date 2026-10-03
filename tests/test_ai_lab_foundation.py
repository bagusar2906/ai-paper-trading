import json
from datetime import datetime, timezone

import pytest

from app.market_data import CompletedCandle, DataQualityEvent, DecisionJournalEntry


def _candle(**overrides):
    values = {
        "source": "mt5",
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "candle_open_time": datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc),
        "open": 2000.0,
        "high": 2003.0,
        "low": 1999.0,
        "close": 2002.0,
        "volume": 123.0,
        "spread": 0.3,
    }
    values.update(overrides)
    return CompletedCandle(**values)


def test_completed_candle_requires_utc_aware_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        _candle(candle_open_time=datetime(2026, 10, 3, 9, 0))


def test_completed_candle_rejects_invalid_range():
    with pytest.raises(ValueError, match="high"):
        _candle(high=1999.0)


def test_completed_candle_upsert_is_idempotent(repos):
    first = repos.market_candles.upsert(_candle())
    updated = repos.market_candles.upsert(_candle(close=2002.5, volume=124.0))

    stored = repos.market_candles.get_all()
    assert len(stored) == 1
    assert first.id == updated.id
    assert stored[0].close == 2002.5
    assert stored[0].volume == 124.0


def test_data_quality_event_is_persisted_with_structured_details(repos):
    entity = repos.data_quality_events.add(DataQualityEvent(
        source="mt5",
        symbol="XAUUSD",
        timeframe="M5",
        event_type="candle_gap",
        details={"missing_bars": 2},
    ))

    assert entity.event_type == "candle_gap"
    assert json.loads(entity.details_json) == {"missing_bars": 2}


def test_decision_journal_keeps_optional_ml_context_paper_only(repos):
    entry = DecisionJournalEntry(
        decision_id="decision-001",
        symbol="XAUUSD",
        timeframe="M5",
        decision_time=datetime(2026, 10, 3, 9, 5, tzinfo=timezone.utc),
        action="HOLD",
        model_id="candidate-xgb-v1",
        regime="trend_up",
        risk_status="rejected",
        gate_outcomes={"data_fresh": True, "probability": False},
        reasons=["probability gate did not pass"],
    )

    repos.decision_journal.add(entry)
    stored = repos.decision_journal.get_by_decision_id("decision-001")

    assert stored is not None
    assert stored.paper_only is True
    assert json.loads(stored.gate_outcomes_json)["data_fresh"] is True
    assert json.loads(stored.reasons_json) == ["probability gate did not pass"]


def test_decision_journal_refuses_non_paper_entries():
    with pytest.raises(ValueError, match="paper-only"):
        DecisionJournalEntry(
            symbol="XAUUSD",
            timeframe="M5",
            decision_time=datetime.now(timezone.utc),
            action="BUY",
            paper_only=False,
        )
