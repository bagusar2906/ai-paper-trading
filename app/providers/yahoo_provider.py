import yfinance as yf
import pandas as pd

from app.providers.base import DataProvider

# Yahoo Finance uses its own interval codes and ticker conventions.
_INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "4h": "60m",   # yfinance has no native 4h bar; resample from 60m if needed
    "1d": "1d",
}

# How far back we can safely ask Yahoo for a given intraday interval.
_PERIOD_MAP = {
    "1m": "7d",
    "5m": "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "60d",
    "1d": "2y",
}

# Yahoo doesn't reliably serve the "XAUUSD=X" spot forex-style ticker (Yahoo
# has intermittently delisted/renamed it). GC=F (COMEX Gold Futures) is the
# stable alternative with real intraday data and volume. Note this is a
# futures price, not spot — usually very close to spot but not identical.
_SYMBOL_MAP = {
    "XAUUSD": "GC=F",
}


class YahooProvider(DataProvider):

    def __init__(self):
        self._connected = False

    def connect(self):
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def is_connected(self):
        return self._connected

    def _resolve_symbol(self, symbol):
        return _SYMBOL_MAP.get(symbol.upper(), symbol)

    def get_history(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        yf_symbol = self._resolve_symbol(symbol)
        interval = _INTERVAL_MAP.get(timeframe, timeframe)
        period = _PERIOD_MAP.get(interval, "60d")

        df = yf.Ticker(yf_symbol).history(period=period, interval=interval)

        if df is None or df.empty:
            raise RuntimeError(
                f"Yahoo Finance returned no data for {yf_symbol} ({timeframe})"
            )

        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        df.index.name = "Time"

        return df.tail(bars)

    def get_latest_bar(self, symbol, timeframe):
        df = self.get_history(symbol, timeframe, 1)
        return df.iloc[-1]

    def get_current_price(self, symbol):
        df = self.get_history(symbol, "1m", 1)
        return float(df["Close"].iloc[-1])
