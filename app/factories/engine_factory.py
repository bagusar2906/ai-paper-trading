from app.factories.provider_factory import create_provider
from app.brokers.paper_broker import PaperBroker
from app.engine.trading_engine import TradingEngine
from app.factories.strategy_factory import create_strategy


def create_engine():

    provider = create_provider()

    strategy = create_strategy()

    broker = PaperBroker()

    return TradingEngine(
        provider=provider,
        strategy=strategy,
        broker=broker,
        symbol="XAUUSD",
        timeframe="15m",
    )