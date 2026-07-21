from app.brokers.paper_broker import PaperBroker
from app.database.base import Base
from app.database.session import create_session_factory
from app.engine.trading_engine import TradingEngine
from app.factories.provider_factory import create_provider
from app.repositories.factory import RepositoryFactory
from app.factories.strategy_factory import create_strategy

from .backtest_response import BacktestResponse
from .equity_point import EquityPoint

from app.api.services.statistic_service import StatisticsService


class BacktestService:

    def run(self, request):

        provider = create_provider()

        try:

            df = provider.get_history(
                request.symbol,
                request.timeframe,
                request.bars,
            )

        finally:

            provider.disconnect()

        strategy = create_strategy()

        engine, backtest_session = create_session_factory(
            "sqlite:///:memory:"
        )
        Base.metadata.create_all(engine)

        repos = RepositoryFactory(
            session_factory=backtest_session
        )

        broker = PaperBroker(
            initial_balance=request.initial_balance,
            repos=repos,
        )

        engine = TradingEngine(
            provider=None,
            strategy=strategy,
            broker=broker,
            symbol=request.symbol,
            timeframe=request.timeframe,
            bars=request.bars,
        )

        #
        # Replay candles
        #
        equity = []

        minimum = strategy.minimum_bars

        for i in range(minimum, len(df)):

            history = df.iloc[: i + 1].copy()

            engine.run_once(history)

            account = broker.get_account()

            equity.append(
                EquityPoint(
                    time=history.iloc[-1].name,
                    equity=account.equity,
                )
            )

        trades = broker.get_trades()

        statistics = StatisticsService().build(
            trades
        )

        return BacktestResponse(
            statistics=statistics,
            equity=equity,
            trades=trades,
        )