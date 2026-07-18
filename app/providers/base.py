"""
base.py

Abstract base class for all market data providers.
"""

from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class DataProvider(ABC):
    """
    Base interface for market data providers.
    """

    @abstractmethod
    def connect(self) -> bool:
        """
        Initialize the provider.

        Returns
        -------
        bool
            True if the connection succeeds.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Close the provider connection.
        """
        pass

    @abstractmethod
    def get_history(
        self,
        symbol: str,
        timeframe: str,
        bars: int
    ) -> pd.DataFrame:
        """
        Retrieve historical OHLCV data.

        Parameters
        ----------
        symbol : str
            Trading symbol (e.g. XAUUSD)
        timeframe : str
            e.g. "1m", "5m", "1h"
        bars : int
            Number of candles to retrieve

        Returns
        -------
        pandas.DataFrame

        Required columns:
            Open
            High
            Low
            Close
            Volume

        Index:
            DatetimeIndex
        """
        pass

    @abstractmethod
    def get_latest_bar(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[pd.Series]:
        """
        Retrieve the latest completed candle.
        """
        pass

    @abstractmethod
    def get_current_price(
        self,
        symbol: str
    ) -> float:
        """
        Return the latest market price.
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check whether the provider is connected.
        """
        pass