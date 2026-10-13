from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class StrategyProfileEntity(Base):

    __tablename__ = "strategy_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(100))

    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("strategies.id")
    )

    symbol: Mapped[str] = mapped_column(String(20))

    timeframe: Mapped[str] = mapped_column(String(10))

    bars: Mapped[int] = mapped_column(Integer)

    initial_balance: Mapped[float]

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )