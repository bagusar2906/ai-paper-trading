from app.analytics.performance_tracker import PerformanceTracker
from app.backtest.backtest_engine import BacktestEngine
from app.brokers.paper_broker import PaperBroker
from app.config import TradingConfig
from app.database.database import create_isolated_engine
from app.database.session import create_session_factory
from app.engine.trading_engine import TradingEngine
from app.providers.factory import create_provider
from app.repositories.factory import RepositoryFactory
from app.strategy.factory import create_strategy


def create_backtest_engine():

    provider = create_provider()

    strategy = create_strategy()

    # Backtests get their own in-memory DB so replaying history never
    # touches the live paper-trading account/positions/trades.
    isolated_engine = create_isolated_engine()
    session_factory = create_session_factory(isolated_engine)
    repos = RepositoryFactory(session=session_factory())

    broker = PaperBroker(
        initial_balance=TradingConfig.INITIAL_BALANCE,
        repos=repos,
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