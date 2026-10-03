import logging

from app.backtest.backtest_result import BacktestResult
from app.backtest.equity_point import EquityPoint
from app.backtest.metrics import maximum_drawdown, sharpe_ratio

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

        # The legacy engine is sampled at each completed candle. A caller can
        # set this explicitly later based on its timeframe; zero means that no
        # annualized Sharpe estimate is reported.
        periods_per_year = getattr(self.engine.broker, "periods_per_year", 0)
        costs = getattr(self.engine.broker, "get_cost_breakdown", lambda: None)()
        fill_timing = getattr(
            getattr(self.engine.broker, "assumptions", None),
            "fill_timing",
            "current_candle_close",
        )

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
            max_drawdown=maximum_drawdown(equity_curve),
            sharpe_ratio=sharpe_ratio(equity_curve, periods_per_year),
            periods_per_year=periods_per_year,
            cost_breakdown=costs,
            fill_timing=fill_timing,
        )
