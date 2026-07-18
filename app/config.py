
# ==================================================
# OANDA
import os
OANDA_API_KEY = os.environ.get("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "")
OANDA_ENV = os.environ.get("OANDA_ENV", "practice")  # "practice" or "live"
# ==================================================


# app/config.py

class TradingConfig:
    SYMBOL = "XAUUSD"
    TIMEFRAME = "5m"
    INITIAL_BALANCE = 10_000
    RISK_PER_TRADE = 0.01


class StrategyConfig:
    EMA_LEN = 20
    RSI_LEN = 3
    RSI_OB = 80
    RSI_OS = 20
    ADX_LEN = 5
    ADX_SMOOTH = 5
    ADX_LEVEL = 30


class ProviderConfig:
    DEFAULT_PROVIDER = "yahoo" # Options: "mt5", "oanda", "yahoo"