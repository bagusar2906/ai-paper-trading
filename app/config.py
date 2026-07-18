# ==================================================
# Application
# ==================================================

DATA_PROVIDER = "yahoo"  # Options: "mt5", "oanda", "yahoo"

# ==================================================
# OANDA
import os
OANDA_API_KEY = os.environ.get("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "")
OANDA_ENV = os.environ.get("OANDA_ENV", "practice")  # "practice" or "live"
# ==================================================

# ==================================================
# Trading
# ==================================================

SYMBOL = "XAUUSD"
TIMEFRAME = "5m"

POINT = 0.01
PIP_SIZE = POINT * 10
CONTRACT_SIZE = 100

# ==================================================
# Strategy
# ==================================================

EMA_LEN = 20

RSI_LEN = 3
RSI_OB = 80
RSI_OS = 20

ADX_LEN = 5
ADX_SMOOTH = 5
ADX_LEVEL = 30