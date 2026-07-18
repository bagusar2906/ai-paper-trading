import pandas as pd

from app.providers.base import DataProvider

try:
    import MetaTrader5 as mt5
except ImportError:
    # MetaTrader5 package only installs on Windows. Importing this module on
    # other platforms (e.g. running tests in CI) shouldn't crash the app;
    # it will only fail if you actually try to use MT5Provider there.
    mt5 = None

_TIMEFRAME_MAP = {
    "1m": "TIMEFRAME_M1",
    "5m": "TIMEFRAME_M5",
    "15m": "TIMEFRAME_M15",
    "30m": "TIMEFRAME_M30",
    "1h": "TIMEFRAME_H1",
    "4h": "TIMEFRAME_H4",
    "1d": "TIMEFRAME_D1",
}


class MT5Provider(DataProvider):

    def __init__(self):
        self._connected = False

    def _require_mt5(self):
        if mt5 is None:
            raise RuntimeError(
                "MetaTrader5 package is not available. MT5Provider only "
                "works on Windows with the MT5 terminal installed."
            )

    def connect(self):
        self._require_mt5()
        self._connected = mt5.initialize()
        return self._connected

    def disconnect(self):
        if self._connected and mt5 is not None:
            mt5.shutdown()
        self._connected = False

    def is_connected(self):
        return self._connected

    def get_history(self, symbol, timeframe, bars):
        self._require_mt5()

        tf_name = _TIMEFRAME_MAP.get(timeframe)
        if tf_name is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        mt5_timeframe = getattr(mt5, tf_name)

        rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, bars)

        if rates is None or len(rates) == 0:
            raise RuntimeError(
                f"MT5 returned no data for {symbol} ({timeframe}): "
                f"{mt5.last_error()}"
            )

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.set_index("time")
        df = df.rename(columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "tick_volume": "Volume",
        })
        df.index.name = "Time"

        return df[["Open", "High", "Low", "Close", "Volume"]]

    def get_latest_bar(self, symbol, timeframe):
        return self.get_history(symbol, timeframe, 1).iloc[-1]

    def get_current_price(self, symbol):
        self._require_mt5()
        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            raise RuntimeError(f"No tick data for {symbol}")

        return tick.bid
