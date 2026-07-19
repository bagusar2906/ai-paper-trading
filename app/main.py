from contextlib import asynccontextmanager
from dataclasses import asdict

from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.dashboard import router as dashboard_router
from app.config import TradingConfig
from app.database.database import init_database
from app.providers.factory import create_provider
from app.strategy import EMARSIADXStrategy
from app.api.chart import router as chart_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="Paper Trading API",
    lifespan=lifespan,
)

# Register API routes
app.include_router(dashboard_router)

app.include_router(chart_router)

# Serve dashboard UI
app.mount(
    "/ui",
    StaticFiles(directory="app/dashboard", html=True),
    name="dashboard",
)

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

        if signal is None:
            return {
                "signal": None
            }
        return asdict(signal)

    finally:
        provider.disconnect()


@app.get("/health")
def health():
    return {"status": "ok"}