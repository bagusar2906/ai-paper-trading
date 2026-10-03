from datetime import datetime

from sqlalchemy import Boolean, DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text, UniqueConstraint

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.database.base import Base


# ==========================================================
# Account
# ==========================================================

class AccountEntity(Base):

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    balance: Mapped[float] = mapped_column(Float)

    equity: Mapped[float] = mapped_column(Float)

    margin: Mapped[float] = mapped_column(Float)

    free_margin: Mapped[float] = mapped_column(Float)

    floating_pnl: Mapped[float] = mapped_column(Float)


# ==========================================================
# Position
# ==========================================================

class PositionEntity(Base):

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(20)
    )

    side: Mapped[str] = mapped_column(
        String(10)
    )

    quantity: Mapped[float] = mapped_column(
        Float
    )

    entry_price: Mapped[float] = mapped_column(
        Float
    )

    current_price: Mapped[float] = mapped_column(
        Float,
        nullable=True,
    )

    floating_pnl: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    stop_loss: Mapped[float] = mapped_column(
        Float,
        nullable=True,
    )

    take_profit: Mapped[float] = mapped_column(
        Float,
        nullable=True,
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

# ==========================================================
# Trade
# ==========================================================

class TradeEntity(Base):

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    symbol: Mapped[str] = mapped_column(String(20))

    side: Mapped[str] = mapped_column(String(10))

    quantity: Mapped[float] = mapped_column(Float)

    entry_price: Mapped[float] = mapped_column(Float)

    exit_price: Mapped[float] = mapped_column(Float)

    pnl: Mapped[float] = mapped_column(Float)

    opened_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    closed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


# ==========================================================
# Signal
# ==========================================================

class SignalEntity(Base):

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    symbol: Mapped[str] = mapped_column(String(20))

    action: Mapped[str] = mapped_column(String(10))

    price: Mapped[float] = mapped_column(Float)

    confidence: Mapped[float] = mapped_column(Float)

    reason: Mapped[str] = mapped_column(String(255))

    stop_loss: Mapped[float] = mapped_column(Float, nullable=True)

    take_profit: Mapped[float] = mapped_column(Float, nullable=True)

    signal_time: Mapped[datetime] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

class SettingEntity(Base):

    __tablename__ = "settings"

    key = mapped_column(
        String(100),
        primary_key=True
    )

    value = mapped_column(
        String(255)
    )

# ==========================================================
# Strategy Profile
# ==========================================================

class StrategyProfileEntity(Base):

    __tablename__ = "strategy_profiles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
    )

    strategy: Mapped[str] = mapped_column(
        String(50),
    )

    parameters_json: Mapped[str] = mapped_column(
        String,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

class StrategyEntity(Base):

    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
    )

    description: Mapped[str] = mapped_column(
        String(500),
        default="",
    )

    strategy_type: Mapped[str] = mapped_column(
        String(50),
    )

    config_json: Mapped[str] = mapped_column(
        String,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )


    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


# ==========================================================
# AI Trading Lab foundation (additive, paper-trading only)
# ==========================================================

class MarketCandleEntity(Base):
    """A normalized, completed market candle captured from a data provider."""

    __tablename__ = "market_candles"
    __table_args__ = (
        UniqueConstraint(
            "source", "symbol", "timeframe", "candle_open_time",
            name="uq_market_candle_source_symbol_timeframe_time",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50))
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str] = mapped_column(String(10))
    candle_open_time: Mapped[datetime] = mapped_column(DateTime)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    spread: Mapped[float | None] = mapped_column(Float, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


class DataQualityEventEntity(Base):
    """An observable data-contract violation or collection anomaly."""

    __tablename__ = "data_quality_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50))
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str] = mapped_column(String(10))
    candle_open_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(100))
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


class DecisionJournalEntity(Base):
    """Paper-only audit record for a decision and its optional ML context."""

    __tablename__ = "decision_journal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[str] = mapped_column(String(64), unique=True)
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str] = mapped_column(String(10))
    decision_time: Mapped[datetime] = mapped_column(DateTime)
    action: Mapped[str] = mapped_column(String(10))
    entry_reference_price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    signal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    regime: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gate_outcomes_json: Mapped[str] = mapped_column(Text, default="{}")
    reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    paper_only: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
