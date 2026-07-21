# app/config.py

import os

# ==========================================================
# OANDA
# ==========================================================

OANDA_API_KEY = os.environ.get("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "")
OANDA_ENV = os.environ.get("OANDA_ENV", "practice")


# ==========================================================
# Application
# ==========================================================

class AppConfig:
    APP_NAME = "Paper Trading Engine"
    DEBUG = True


# ==========================================================
# Provider
# ==========================================================

class ProviderConfig:

    DEFAULT_PROVIDER = "yahoo"      # yahoo | mt5 | oanda

    YAHOO_SYMBOL = "GC=F"

    MT5_SYMBOL = "XAUUSD"

    OANDA_SYMBOL = "XAU_USD"


# ==========================================================
# Strategy
# ==========================================================

class StrategyConfig:

    NAME = "ema_rsi_adx"

    EMA_LEN = 20

    RSI_LEN = 3
    RSI_OB = 80
    RSI_OS = 20

    ADX_LEN = 5
    ADX_SMOOTH = 5
    ADX_LEVEL = 30

    MINIMUM_BARS = 100

    # Stop loss / take profit sizing for signals that open a trade.
    # XAUUSD on this broker: point = 0.01, 1 pip = 0.1 price units,
    # so 50 pips = 5.0 price units (~$5 on gold).
    STOP_LOSS_PIPS = 50
    RISK_REWARD_RATIO = 2.0


# ==========================================================
# Trading
# ==========================================================

class TradingConfig:

    INITIAL_BALANCE = 10000.0

    SYMBOL = "XAUUSD"

    TIMEFRAME = "M5"

    HISTORY_BARS = 300

    INITIAL_BALANCE = 10_000

    DEFAULT_QUANTITY = 1.0

    RISK_PER_TRADE = 0.01

    POINT = 0.01

    PIP_SIZE = POINT * 10

    CONTRACT_SIZE = 100


# ==========================================================
# Database
# ==========================================================

class DatabaseConfig:

    SQLITE_DB = "paper_trading.db"


# ==========================================================
# Worker
# ==========================================================

class WorkerConfig:

    INTERVAL_SECONDS = 300