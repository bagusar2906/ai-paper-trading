from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from app.models.signal import TradingSignal
from app.strategy.parameter import StrategyParameter


class Strategy(ABC):
    """
    Base class for all trading strategies.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Strategy display name.
        """
        pass

    # NEW
    @classmethod
    @abstractmethod
    def schema(cls) -> list[StrategyParameter]:
        """
        Returns the editable parameter schema
        used by the UI.
        """
        pass

    @property
    def minimum_bars(self) -> int:
        """
        Minimum number of candles required before
        the strategy can generate signals.
        """
        return 100

    @abstractmethod
    def prepare(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Calculate indicators.
        """
        pass

    @abstractmethod
    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
    ) -> Optional[TradingSignal]:
        """
        Generate BUY / SELL signal.
        """
        pass

    def validate_data(
        self,
        df: pd.DataFrame,
    ) -> bool:

        if df is None:
            return False

        if df.empty:
            return False

        required = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        return all(
            column in df.columns
            for column in required
        )

    def can_run(
        self,
        df: pd.DataFrame,
    ) -> bool:

        return (
            self.validate_data(df)
            and len(df) >= self.minimum_bars
        )