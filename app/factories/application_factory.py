from app.brokers.paper_broker import PaperBroker
from app.engine.trading_engine import TradingEngine
from app.factories.provider_factory import create_provider
from app.factories.repository_factory import RepositoryFactory
from app.factories.strategy_factory import create_strategy
from app.factories.strategy_loader import load_active_strategy


class ApplicationFactory:

    @staticmethod
    def create_engine():

        repos = RepositoryFactory()

        provider = create_provider()

        strategy = load_active_strategy()

        broker = PaperBroker(
            repos=repos
        )

        return TradingEngine(
            provider=provider,
            strategy=strategy,
            broker=broker,
            symbol="XAUUSD",
            timeframe="15m",
        )

    @staticmethod
    def create_backtest_engine(
        repos,
        provider,
        strategy,
        broker,
        symbol,
        timeframe,
        bars,
    ):

        return TradingEngine(
            provider=provider,
            strategy=strategy,
            broker=broker,
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
        )