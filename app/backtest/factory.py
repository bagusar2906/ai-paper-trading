from app.analytics.performance_tracker import PerformanceTracker
from app.backtest.backtest_engine import BacktestEngine
from app.brokers.paper_broker import PaperBroker
from app.config import TradingConfig
from app.engine.trading_engine import TradingEngine
from app.providers.factory import create_provider
from app.strategy.factory import create_strategy


def create_backtest_engine():

    provider = create_provider()

    strategy = create_strategy()

    broker = PaperBroker(
        initial_balance=TradingConfig.INITIAL_BALANCE,
    )

    engine = TradingEngine(
        provider,
        strategy,
        broker,
        TradingConfig.SYMBOL,
        TradingConfig.TIMEFRAME,
    )

    tracker = PerformanceTracker()

    return BacktestEngine(
        engine,
        provider,
        tracker,
    )