from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.backtest import router as backtest_router
from app.api.chart import router as chart_router
from app.api.dashboard import router as dashboard_router
from app.api.order import router as order_router
from app.api.quote import router as quote_router
from app.api.position import router as position_router
from app.api.routes.strategy_profile_router import router as strategy_profile_router
from app.api.settings import router as settings_router
from app.database.database import init_database
from app.database.database_initializer import initialize_database
from app.factories.repository_factory import RepositoryFactory
from app.scheduler.trading_scheduler import TradingScheduler
from app.services.signal_service import SignalService
from app.strategy.strategy_router import router as strategy_router



scheduler = TradingScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):

    #
    # Create database tables
    #
    init_database()

    #
    # Seed default data (only once)
    #
    initialize_database()

    #
    # Start background trading
    #
    scheduler.start()

    try:

        yield

    finally:

        scheduler.stop()


app = FastAPI(
    title="Paper Trading API",
    lifespan=lifespan,
)

# shutdown handled in lifespan


# Register API routes
app.include_router(dashboard_router)
app.include_router(chart_router)
app.include_router(backtest_router)
app.include_router(order_router)
app.include_router(quote_router)
app.include_router(position_router)
app.include_router(settings_router)
app.include_router(strategy_profile_router)
app.include_router(strategy_router)

# Serve dashboard UI
app.mount(
    "/ui",
    StaticFiles(directory="app/dashboard", html=True),
    name="dashboard",
)


@app.get("/signal")
def current_signal():
    service = SignalService()

    try:
        signal = service.generate()
    finally:
        service.close()

    if signal is None:
        return {"signal": None}

    # Persist so this also shows up in signal history / chart markers,
    # not just when the background trading worker runs. Skip if it's the
    # same action as the last one saved, to avoid flooding history with
    # repeated identical signals.
    repos = RepositoryFactory()
    try:
        last = repos.signals.get_last(signal.symbol)
        if last is None or last.action != signal.action:
            repos.signals.add(signal)
    finally:
        repos.close()

    return asdict(signal)


@app.get("/health")
def health():
    return {"status": "ok"}
