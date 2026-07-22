from app.analytics.performance_tracker import PerformanceTracker
from app.backtest.backtest_engine import BacktestEngine
from app.brokers.paper_broker import PaperBroker
from app.config import TradingConfig
from app.database.base import Base
from app.database.session import create_session_factory
from app.engine.trading_engine import TradingEngine
from app.factories.provider_factory import create_provider
from app.factories.repository_factory import RepositoryFactory
from app.factories.strategy_factory import create_strategy


def create_backtest_engine():

    provider = create_provider()

    strategy = create_strategy()

    # Backtests get their own in-memory DB so replaying history never
    # touches the live paper-trading account/positions/trades.
    #
    # create_session_factory() takes a database URL (it builds the engine
    # internally) and hands back (engine, Session) — it does NOT accept an
    # already-built engine, and it does NOT return a bare callable.
    isolated_engine, Session = create_session_factory(
        "sqlite:///:memory:"
    )

    Base.metadata.create_all(isolated_engine)

    repos = RepositoryFactory(session=Session())

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