from dataclasses import asdict

from fastapi import APIRouter

from app.backtest.factory import create_backtest_engine
from app.config import TradingConfig

router = APIRouter()


@router.get("/backtest")
def run_backtest(bars: int = 1000):
    """
    Replay recent history through the live strategy/risk/broker pipeline
    and return performance statistics. Runs against an isolated in-memory
    DB — never touches the live paper-trading account/positions/trades.
    """

    backtest = create_backtest_engine()

    try:
        result = backtest.run(
            TradingConfig.SYMBOL,
            TradingConfig.TIMEFRAME,
            bars,
        )
    finally:
        backtest.engine.close()
        backtest.provider.disconnect()

    return asdict(result)
