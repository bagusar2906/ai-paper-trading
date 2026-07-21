from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String

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