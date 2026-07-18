from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI

from app.providers.factory import create_provider
from app.strategy import EMARSIADXStrategy
from app.database.database import init_db, save_signal, get_recent_signals
from app.config import TradingConfig


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Paper Trading API", lifespan=lifespan)

strategy = EMARSIADXStrategy()

# Enough bars for indicator warmup (EMA/RSI/ADX) plus signal history.
HISTORY_BARS = 300


@app.get("/signal")
def current_signal():
    provider = create_provider()
    try:
        df = provider.get_history(TradingConfig.SYMBOL, TradingConfig.TIMEFRAME, HISTORY_BARS)
        signal = strategy.generate_signal(TradingConfig.SYMBOL, df)
    finally:
        provider.disconnect()

    signal_dict = asdict(signal)

    save_signal({
        "symbol": signal_dict["symbol"],
        "signal": signal_dict["action"],
        "price": signal_dict["price"],
        "rsi": signal_dict["rsi"],
        "adx": signal_dict["adx"],
        "ema": signal_dict["ema"],
        "time": signal_dict["time"],
    })

    return signal_dict


@app.get("/history")
def history(limit: int = 20):
    return get_recent_signals(limit)


@app.get("/health")
def health():
    return {"status": "ok"}
