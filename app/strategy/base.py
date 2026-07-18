from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class TradingSignal:
    """
    Output of a trading strategy.
    """

    symbol: str

    action: str            # BUY | SELL | HOLD

    price: float

    time: str

    reason: str = ""

    stop_loss: Optional[float] = None

    take_profit: Optional[float] = None

    confidence: float = 1.0

    metadata: Optional[dict] = None


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
    ) -> TradingSignal:
        """
        Generate BUY / SELL / HOLD signal.
        """
        pass

    def validate_data(
        self,
        df: pd.DataFrame
    ) -> bool:
        """
        Basic validation before running strategy.
        """

        required = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        return all(col in df.columns for col in required)