from app.providers.factory import create_provider
from app.strategy.factory import create_strategy
from app.brokers.paper_broker import PaperBroker

from app.config import TradingConfig


from app.engine.trading_engine import TradingEngine


def create_engine():

    provider = create_provider()

    strategy = create_strategy()

    broker = PaperBroker()

    return TradingEngine(
        provider,
        strategy,
        broker,
        TradingConfig.SYMBOL,
        TradingConfig.TIMEFRAME,
    )