"""Point-in-time-safe records for the AI Trading Lab foundation.

These contracts intentionally do not alter the existing provider DataFrame
interface. A later collector can adapt completed provider candles into them.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware UTC values")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class CompletedCandle:
    source: str
    symbol: str
    timeframe: str
    candle_open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    spread: float | None = None
    ingested_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self):
        if not all((self.source, self.symbol, self.timeframe)):
            raise ValueError("source, symbol, and timeframe are required")
        if self.high < max(self.open, self.close):
            raise ValueError("high must be at least open and close")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be at most open and close")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")
        if self.spread is not None and self.spread < 0:
            raise ValueError("spread cannot be negative")
        object.__setattr__(self, "candle_open_time", _utc_timestamp(self.candle_open_time))
        object.__setattr__(self, "ingested_at", _utc_timestamp(self.ingested_at))


@dataclass(frozen=True)
class DataQualityEvent:
    source: str
    symbol: str
    timeframe: str
    event_type: str
    details: dict[str, Any] = field(default_factory=dict)
    candle_open_time: datetime | None = None

    def __post_init__(self):
        if not all((self.source, self.symbol, self.timeframe, self.event_type)):
            raise ValueError("source, symbol, timeframe, and event_type are required")
        if self.candle_open_time is not None:
            object.__setattr__(
                self,
                "candle_open_time",
                _utc_timestamp(self.candle_open_time),
            )


@dataclass(frozen=True)
class DecisionJournalEntry:
    symbol: str
    timeframe: str
    decision_time: datetime
    action: str
    entry_reference_price: float | None = None
    decision_id: str = field(default_factory=lambda: uuid4().hex)
    signal_id: int | None = None
    model_id: str | None = None
    regime: str | None = None
    risk_status: str | None = None
    gate_outcomes: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    paper_only: bool = True

    def __post_init__(self):
        if not all((self.symbol, self.timeframe, self.action, self.decision_id)):
            raise ValueError("symbol, timeframe, action, and decision_id are required")
        if not self.paper_only:
            raise ValueError("AI Trading Lab decision journaling is paper-only")
        object.__setattr__(self, "decision_time", _utc_timestamp(self.decision_time))
