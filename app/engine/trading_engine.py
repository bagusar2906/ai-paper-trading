import logging

from app.engine.result import EngineResult
from app.enums.trading_mode import TradingMode
from app.managers.position_manager import PositionManager
from app.risk.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class TradingEngine:

    def __init__(
        self,
        provider,
        strategy,
        broker,
        symbol,
        timeframe,
        bars=300,
    ):
        self.provider = provider
        self.strategy = strategy
        self.broker = broker

        self.symbol = symbol
        self.timeframe = timeframe
        self.bars = bars

        self.position_manager = PositionManager(self.broker)
        self.risk_manager = RiskManager()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run_once(self, df=None):

        #
        # Load market data
        #
        if df is None:
            df = self._load_data()

        #
        # Validate data
        #
        if not self.strategy.can_run(df):

            logger.warning(
                "Not enough bars to run strategy"
            )

            return EngineResult(
                account=self.get_account(),
                message="Not enough data",
            )

        #
        # Calculate indicators
        #
        df = self._prepare_data(df)

        #
        # Latest market price
        #
        current_price = self._get_current_price(df)

        #
        # Update floating P/L
        #
        self.broker.update_market_price(
            self.symbol,
            current_price,
        )

        #
        # Check TP / SL
        #
        closed_trades = self.position_manager.update(
            self.symbol,
            current_price,
        )

        #
        # Generate signal
        #
        signal = self._generate_signal(df)

        #
        # Execute trade
        #
        if signal is not None:

            self._execute_signal(signal)

        #
        # Return result
        #
        return self._build_result(
            signal,
            closed_trades,
        )

    def get_account(self):

        return self.broker.get_account()

    def get_trades(self):

        return self.broker.get_trades()

    def close(self):

        self.broker.close()

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _load_data(self):

        logger.debug(
            "Loading %d bars for %s",
            self.bars,
            self.symbol,
        )

        return self.provider.get_history(
            self.symbol,
            self.timeframe,
            self.bars,
        )

    def _prepare_data(self, df):

        logger.debug(
            "Preparing indicators"
        )

        return self.strategy.prepare(df)

    def _get_current_price(self, df):

        #
        # Works whether the dataframe still uses
        # Close or has been renamed to close.
        #
        if "close" in df.columns:
            return float(df.iloc[-1]["close"])

        return float(df.iloc[-1]["Close"])

    def _generate_signal(self, df):

        signal = self.strategy.generate_signal(
            self.symbol,
            df,
        )

        logger.info(
            "Signal generated: %s",
            signal.action,
        )

        last = self.broker.repos.signals.get_last(
            self.symbol
        )

        if last is None or last.action != signal.action:

            self.broker.repos.signals.add(signal)

        else:

            logger.debug(
                "Skipping duplicate consecutive %s signal for %s",
                signal.action,
                self.symbol,
            )

        return signal

    def _execute_signal(self, signal):

        if signal is None:
            return


        self.broker.process_signal(signal)

        account = self.get_account()

        positions = self.broker.get_positions()

        decision = self.risk_manager.evaluate(
            signal,
            account,
            positions,
        )

        if not decision.allowed:

            logger.info(
                "Trade rejected: %s",
                decision.reason,
            )

            return

        signal.quantity = decision.quantity

        logger.info(
            "Executing %s %.2f lot(s)",
            signal.action,
            signal.quantity,
        )

        self.broker.execute(signal)

    def _build_result(
        self,
        signal,
        closed_trades,
    ):

        positions = self.broker.get_positions()

        return EngineResult(
            signal=signal,
            position=positions[-1] if positions else None,
            closed_trades=closed_trades,
            account=self.get_account(),
            message="Completed",
        )