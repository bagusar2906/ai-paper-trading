import requests
import pandas as pd

from app.providers.base import DataProvider
from app.config import OANDA_ENV, OANDA_ACCOUNT_ID

_GRANULARITY_MAP = {
    "1m": "M1",
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "H1",
    "4h": "H4",
    "1d": "D",
}

# OANDA instrument codes use an underscore between base and quote.
_SYMBOL_MAP = {
    "XAUUSD": "XAU_USD",
}


class OandaProvider(DataProvider):

    def __init__(self, api_key):
        self.api_key = api_key
        self._connected = False
        self._base_url = (
            "https://api-fxpractice.oanda.com"
            if OANDA_ENV == "practice"
            else "https://api-fxtrade.oanda.com"
        )

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def connect(self):
        if not self.api_key:
            raise RuntimeError(
                "OANDA_API_KEY is not set. Set it via the OANDA_API_KEY "
                "environment variable."
            )
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def is_connected(self):
        return self._connected

    def _resolve_symbol(self, symbol):
        return _SYMBOL_MAP.get(symbol.upper(), symbol)

    def get_history(self, symbol, timeframe, bars):
        instrument = self._resolve_symbol(symbol)
        granularity = _GRANULARITY_MAP.get(timeframe)

        if granularity is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        url = f"{self._base_url}/v3/instruments/{instrument}/candles"
        params = {"count": bars, "granularity": granularity, "price": "M"}

        resp = requests.get(url, headers=self._headers(), params=params, timeout=10)
        resp.raise_for_status()
        candles = resp.json().get("candles", [])

        if not candles:
            raise RuntimeError(f"OANDA returned no candles for {instrument}")

        rows = []
        index = []
        for c in candles:
            if not c.get("complete", True):
                continue
            mid = c["mid"]
            rows.append({
                "Open": float(mid["o"]),
                "High": float(mid["h"]),
                "Low": float(mid["l"]),
                "Close": float(mid["c"]),
                "Volume": float(c.get("volume", 0)),
            })
            index.append(pd.to_datetime(c["time"]))

        df = pd.DataFrame(rows, index=pd.DatetimeIndex(index, name="Time"))
        return df

    def get_latest_bar(self, symbol, timeframe):
        return self.get_history(symbol, timeframe, 1).iloc[-1]

    def get_current_price(self, symbol):
        if not OANDA_ACCOUNT_ID:
            raise RuntimeError(
                "OANDA_ACCOUNT_ID is not set. Set it via the "
                "OANDA_ACCOUNT_ID environment variable."
            )

        instrument = self._resolve_symbol(symbol)
        url = f"{self._base_url}/v3/accounts/{OANDA_ACCOUNT_ID}/pricing"
        params = {"instruments": instrument}

        resp = requests.get(url, headers=self._headers(), params=params, timeout=10)
        resp.raise_for_status()
        prices = resp.json().get("prices", [])

        if not prices:
            raise RuntimeError(f"OANDA returned no price for {instrument}")

        return float(prices[0]["bids"][0]["price"])
