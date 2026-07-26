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

    # Lowercase
    "1m": "TIMEFRAME_M1",
    "5m": "TIMEFRAME_M5",
    "15m": "TIMEFRAME_M15",
    "30m": "TIMEFRAME_M30",
    "1h": "TIMEFRAME_H1",
    "4h": "TIMEFRAME_H4",
    "1d": "TIMEFRAME_D1",

    # MT5 style
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",

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

    def _require_connected(self):
        self._require_mt5()

        if not self._connected:
            raise RuntimeError(
                "MT5Provider is not connected - call connect() first, "
                "or the connection dropped (terminal closed/logged out)."
            )

    def connect(self):
        self._require_mt5()

        self._connected = mt5.initialize()

        if not self._connected:
            code, message = mt5.last_error()
            raise RuntimeError(
                f"MT5 terminal connection failed ({code}: {message}). "
                "Common causes: the MT5 terminal app isn't running or "
                "isn't logged in, 'Algo Trading' is disabled in the "
                "terminal, or a 32-bit/64-bit Python mismatch. See "
                "mt5.initialize() docs for the full error code list."
            )

        return self._connected

    def disconnect(self):
        if self._connected and mt5 is not None:
            mt5.shutdown()
        self._connected = False

    def is_connected(self):
        return self._connected

    def get_history(self, symbol, timeframe, bars):
        self._require_connected()

        tf_name = _TIMEFRAME_MAP.get(timeframe)
        if tf_name is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        mt5_timeframe = getattr(mt5, tf_name)

        rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, bars)

        if rates is None or len(rates) == 0:
            code, message = mt5.last_error()

            if code == -10004:
                # Connection was live at connect() time but has since
                # dropped (terminal closed, logged out, or lost its
                # connection to the broker server).
                self._connected = False
                raise RuntimeError(
                    f"Lost connection to the MT5 terminal ({code}: "
                    f"{message}). Check that the terminal is still open "
                    "and logged in, then reconnect."
                )

            raise RuntimeError(
                f"MT5 returned no data for {symbol} ({timeframe}): "
                f"{code}: {message}"
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
        self._require_connected()
        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            raise RuntimeError(f"No tick data for {symbol}")

        return tick.bid
