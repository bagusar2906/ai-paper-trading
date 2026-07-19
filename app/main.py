from dataclasses import asdict

from fastapi import FastAPI

from app.config import TradingConfig
from app.providers.factory import create_provider
from app.strategy import EMARSIADXStrategy

app = FastAPI(title="Paper Trading API")

strategy = EMARSIADXStrategy()

HISTORY_BARS = 300


@app.get("/signal")
def current_signal():

    provider = create_provider()

    try:
        df = provider.get_history(
            TradingConfig.SYMBOL,
            TradingConfig.TIMEFRAME,
            HISTORY_BARS,
        )

        signal = strategy.generate_signal(
            TradingConfig.SYMBOL,
            df,
        )

    finally:
        provider.disconnect()

    return asdict(signal)


@app.get("/health")
def health():

    return {
        "status": "ok"
    }