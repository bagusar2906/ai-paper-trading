import logging

from app.engine.result import EngineResult
from app.managers.position_manager import PositionManager
from app.managers.risk_manager import RiskManager

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

    def run_once(self):

        #
        # Load market data
        #

        df = self._load_data()

        #
        # Validate data
        #

        if not self.strategy.can_run(df):

            logger.warning("Not enough bars to run strategy")

            return EngineResult(
                account=self.broker.get_account(),
                message="Not enough data",
            )

        #
        # Calculate indicators
        #

        df = self._prepare_data(df)

        #
        # Generate signal
        #

        signal = self._generate_signal(df)

        #
        # Execute trade
        #

        self._execute_signal(signal)

        #
        # Update existing positions (SL / TP)
        #
        current_price = df.iloc[-1]["Close"]

        closed_trades = self.position_manager.update(
            self.symbol,
            current_price,
        )

        signal = self._generate_signal(df)

        self._execute_signal(signal)

        return self._build_result(
            signal,
            closed_trades,
        )

    # ------------------------------------------------------------------
    # Private helpers
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

        logger.debug("Preparing indicators")

        return self.strategy.prepare(df)

    def _generate_signal(self, df):

        signal = self.strategy.generate_signal(
            self.symbol,
            df,
        )

        logger.info(
            "Signal generated: %s",
            signal.action if signal else "None",
        )

        return signal

    def _execute_signal(self, signal):

        if signal is None:
            return

        if self.risk_manager.can_open_position(
            signal,
            self.broker.get_account(),
            self.broker.get_positions(),
        ):

            logger.info(
                "Executing %s signal",
                signal.action,
            )

            self.broker.execute(signal)

        else:

            logger.info(
                "Risk manager rejected signal"
            )

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
            account=self.broker.get_account(),
            message="Completed",
        )