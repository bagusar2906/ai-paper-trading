import logging

from app.backtest.backtest_result import BacktestResult
from app.backtest.equity_point import EquityPoint

logger = logging.getLogger(__name__)


class BacktestEngine:

    def __init__(
        self,
        engine,
        provider,
        tracker,
    ):
        self.engine = engine
        self.provider = provider
        self.tracker = tracker

    def run(
        self,
        symbol,
        timeframe,
        bars,
    ):

        logger.info(
            "Starting backtest for %s (%s)",
            symbol,
            timeframe,
        )

        #
        # Download historical data
        #

        history = self.provider.get_history(
            symbol,
            timeframe,
            bars,
        )

        logger.info(
            "Loaded %d bars",
            len(history),
        )

        #
        # Warmup period
        #

        warmup = self.engine.bars

        #
        # Replay history candle-by-candle
        #

        for i in range(warmup, len(history)):

            df = history.iloc[: i + 1]

            self.engine.run_once(df)

        #
        # Calculate statistics
        #

        trades = self.engine.broker.get_trades()

        statistics = self.tracker.calculate(trades)

        account = self.engine.broker.get_account()

        equity_curve = [
            EquityPoint(
                time=point["time"],
                equity=point["equity"],
            )
            for point in self.engine.equity_history
        ]

        logger.info(
            "Backtest finished. Trades=%d NetProfit=%.2f",
            statistics.total_trades,
            statistics.net_profit,
        )

        return BacktestResult(
            statistics=statistics,
            trades=trades,
            equity_curve=equity_curve,
            start_balance=self.engine.broker.initial_balance,
            end_balance=account.balance,
            bars_processed=len(history),
        )