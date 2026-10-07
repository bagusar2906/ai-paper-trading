"""Twelve Data REST market-data provider.

The provider always requests timestamps in UTC and excludes the candle that is
currently forming.  Strategies therefore make one decision from a completed
candle, even when the scheduler starts midway through a timeframe.
"""

import pandas as pd
import requests

from app.providers.base import DataProvider


_INTERVAL_MAP = {
    "M1": "1min", "1m": "1min",
    "M5": "5min", "5m": "5min",
    "M15": "15min", "15m": "15min",
    "M30": "30min", "30m": "30min",
    "H1": "1h", "1h": "1h",
    "H4": "4h", "4h": "4h",
    "D1": "1day", "1d": "1day",
}

_FREQUENCY_MAP = {
    "1min": "min", "5min": "5min", "15min": "15min",
    "30min": "30min", "1h": "h", "4h": "4h", "1day": "D",
}

_SYMBOL_MAP = {"XAUUSD": "XAU/USD"}


class TwelveDataProvider(DataProvider):
    """Retrieve spot XAU/USD OHLCV data from Twelve Data."""

    source_name = "twelve_data"

    def get_history_range(self, symbol, timeframe, start, end):
        self._require_connected()
        payload = self._get("time_series", {"symbol": self._resolve_symbol(symbol),
                            "interval": self._interval(timeframe), "timezone": "UTC",
                            "start_date": start.strftime("%Y-%m-%d %H:%M:%S"),
                            "end_date": end.strftime("%Y-%m-%d %H:%M:%S"), "outputsize": 5000})
        values = payload.get("values", [])
        if not values:
            return pd.DataFrame()
        frame = pd.DataFrame(values)
        frame.index = pd.to_datetime(frame.pop("datetime"), utc=True)
        frame = frame.rename(columns={"open": "Open", "high": "High", "low": "Low",
                                      "close": "Close", "volume": "Volume"})
        if "Volume" not in frame:
            frame["Volume"] = 0.0
        frame = frame[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="raise")
        return frame[(frame.index >= start) & (frame.index < end)].sort_index()

    BASE_URL = "https://api.twelvedata.com"

    def __init__(self, api_key: str, session=requests):
        self.api_key = api_key
        self._session = session
        self._connected = False

    def connect(self):
        if not self.api_key:
            raise RuntimeError(
                "TWELVE_DATA_API_KEY is not set. Create a free Twelve Data "
                "API key, then set it before starting the app."
            )
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def is_connected(self):
        return self._connected

    def _require_connected(self):
        if not self._connected:
            raise RuntimeError("Twelve Data provider is not connected.")

    @staticmethod
    def _resolve_symbol(symbol):
        return _SYMBOL_MAP.get(symbol.upper(), symbol)

    @staticmethod
    def _interval(timeframe):
        interval = _INTERVAL_MAP.get(timeframe)
        if interval is None:
            raise ValueError(f"Unsupported Twelve Data timeframe: {timeframe}")
        return interval

    def _get(self, endpoint, params):
        response = self._session.get(
            f"{self.BASE_URL}/{endpoint}",
            params={**params, "apikey": self.api_key},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "error" or payload.get("code", 0) >= 400:
            raise RuntimeError(payload.get("message", "Twelve Data request failed."))
        return payload

    def get_history(self, symbol, timeframe, bars):
        self._require_connected()
        interval = self._interval(timeframe)
        payload = self._get("time_series", {
            "symbol": self._resolve_symbol(symbol),
            "interval": interval,
            # Fetch one extra record because the current candle is excluded.
            "outputsize": min(bars + 1, 5000),
            "timezone": "UTC",
        })
        values = payload.get("values", [])
        if not values:
            raise RuntimeError("Twelve Data returned no candle data.")

        df = pd.DataFrame(values)
        if "datetime" not in df:
            raise RuntimeError("Twelve Data response did not contain timestamps.")

        df["Time"] = pd.to_datetime(df.pop("datetime"), utc=True)
        df = df.set_index("Time").sort_index()
        df = df.rename(columns={
            "open": "Open", "high": "High", "low": "Low", "close": "Close",
            "volume": "Volume",
        })
        for column in ("Open", "High", "Low", "Close"):
            if column not in df:
                raise RuntimeError(f"Twelve Data response is missing {column}.")
            df[column] = pd.to_numeric(df[column], errors="coerce")
        if "Volume" in df:
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)
        else:
            # Twelve Data forex / precious-metal candles do not include
            # exchange volume, but downstream strategies require the column.
            df["Volume"] = 0.0
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()

        # Candle timestamps mark the start of the interval.  Remove the open
        # interval so a strategy never acts on a price that is still changing.
        current_start = pd.Timestamp.now(tz="UTC").floor(_FREQUENCY_MAP[interval])
        df = df[df.index < current_start]
        if df.empty:
            raise RuntimeError("Twelve Data has no completed candles yet.")
        return df.tail(bars)

    def get_latest_bar(self, symbol, timeframe):
        return self.get_history(symbol, timeframe, 1).iloc[-1]

    def get_current_price(self, symbol):
        self._require_connected()
        payload = self._get("price", {"symbol": self._resolve_symbol(symbol)})
        try:
            return float(payload["price"])
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Twelve Data returned an invalid price.") from error
