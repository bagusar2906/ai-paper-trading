
from app.factories.provider_factory import create_provider
from app.brokers.paper_broker import PaperBroker
from app.engine.trading_engine import TradingEngine
from app.factories.repository_factory import RepositoryFactory
from app.factories.strategy_factory import create_strategy


def create_engine():

    repos = RepositoryFactory()

    try:

        entity = repos.strategies.get_active()

        if entity is None:
            raise Exception("No active strategy.")

        print(type(entity.config))
        print(entity.config)

        provider = create_provider()
        strategy = create_strategy(
            entity.strategy_type,
            entity.config,
        )

    finally:
        repos.close()

    broker = PaperBroker()


    return TradingEngine(
        provider=provider,
        strategy=strategy,
        broker=broker,
        symbol="XAUUSD",
        timeframe="15m",
    )