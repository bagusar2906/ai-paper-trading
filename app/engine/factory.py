from app.providers.factory import create_provider
from app.strategy.factory import create_strategy
from app.brokers.paper_broker import PaperBroker
from app.engine.trading_engine import TradingEngine
from app.config import TradingConfig

# NEW
from app.database.database import init_database


def create_engine():

    # Ensure database tables exist
    init_database()

    provider = create_provider()

    strategy = create_strategy()

    broker = PaperBroker(
        initial_balance=TradingConfig.INITIAL_BALANCE
    )

    return TradingEngine(
        provider,
        strategy,
        broker,
        TradingConfig.SYMBOL,
        TradingConfig.TIMEFRAME,
    )