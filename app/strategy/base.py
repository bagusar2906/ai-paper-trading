from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from app.models.signal import TradingSignal


class Strategy(ABC):
    """
    Base class for all trading strategies.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Strategy name.
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
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate indicators.

        Returns
        -------
        DataFrame with indicator columns added.
        """
        pass

    @abstractmethod
    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
    ) -> Optional[TradingSignal]:
        """
        Generate a BUY / SELL signal.

        Returns
        -------
        TradingSignal or None if no signal.
        """
        pass

    def validate_data(
        self,
        df: pd.DataFrame
    ) -> bool:
        """
        Validate input market data.
        """

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

        return all(col in df.columns for col in required)

    def can_run(
        self,
        df: pd.DataFrame
    ) -> bool:
        """
        Check whether the strategy has enough data to run.
        """

        return (
            self.validate_data(df)
            and len(df) >= self.minimum_bars
        )