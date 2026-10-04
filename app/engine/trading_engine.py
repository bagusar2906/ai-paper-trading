import logging

from app.engine.result import EngineResult
from app.enums.trading_mode import TradingMode
from app.managers.position_manager import PositionManager
from app.models import account
from app.risk.risk_manager import RiskManager
from app.market_data import DecisionJournalEntry

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
        respect_trading_mode=True,
    ):
        self.provider = provider
        self.strategy = strategy
        self.broker = broker

        self.symbol = symbol
        self.timeframe = timeframe
        self.bars = bars

        self.respect_trading_mode = respect_trading_mode

        self.equity_history = []

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
        current_time = df.index[-1]

        # Cost-aware backtests queue a decision at candle close and fill it at
        # the following candle open. Production paper brokers do not expose
        # this optional hook, so their current execution behavior is unchanged.
        advance_candle = getattr(self.broker, "advance_candle", None)
        if advance_candle is not None:
            advance_candle(
                self.symbol,
                self._get_current_open(df),
                current_time,
            )

        #
        # Update floating P/L
        #
        self.broker.update_market_price(
            self.symbol,
            current_price
        )

        account = self.get_account()

        self.equity_history.append({
            "time": current_time,
            "equity": account.equity,
        })

        account = self.get_account()

        self.equity_history.append({
            "time": current_time,
            "equity": account.equity,
        })

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

    def _get_current_open(self, df):
        if "open" in df.columns:
            return float(df.iloc[-1]["open"])
        return float(df.iloc[-1]["Open"])

    def _generate_signal(self, df):

        signal = self.strategy.generate_signal(
            self.symbol,
            df,
        )

        logger.debug(
            "Signal generated: %s",
            signal.action,
        )

        # Live paper execution persists decisions through its repository. Pure
        # in-memory backtest brokers intentionally have no database session.
        repos = getattr(self.broker, "repos", None)
        if repos is not None:
            repos.signals.upsert_for_candle(signal)

        return signal

    def _execute_signal(self, signal):

        if signal is None:
            return

        context = getattr(signal, "ai_lab_context", None)

        if self.respect_trading_mode:

            mode = self.broker.get_trading_mode()

            if mode != TradingMode.AUTO:

                self._journal_ai_decision(signal, context, "not_auto")

                logger.debug(
                    "Trading mode is %s - signal recorded, "
                    "not auto-executing",
                    mode,
                )

                return

        account = self.get_account()

        positions = self.broker.get_positions()

        decision = self.risk_manager.evaluate(
            signal,
            account,
            positions,
        )

        if not decision.allowed:

            self._journal_ai_decision(signal, context, "rejected")

            logger.info(
                "Trade rejected: %s",
                decision.reason,
            )

            return

        if not self._journal_ai_decision(signal, context, "approved"):
            logger.error("AI-assisted paper trade rejected because its decision could not be journaled")
            return

        signal.quantity = decision.quantity

        logger.info(
            "Executing %s %.2f lot(s)",
            signal.action,
            signal.quantity,
        )

        self.broker.execute(signal)

    def _journal_ai_decision(self, signal, context, risk_status):
        if context is None:
            return True
        repos = getattr(self.broker, "repos", None)
        if repos is None:
            return True
        try:
            repos.decision_journal.add(DecisionJournalEntry(
                decision_id=context["decision_id"],
                symbol=signal.symbol,
                timeframe=self.timeframe,
                decision_time=signal.time,
                action=getattr(signal.action, "value", str(signal.action)),
                entry_reference_price=signal.price,
                model_id=context["model_id"],
                regime=context["regime"],
                risk_status=risk_status,
                gate_outcomes=context["gates"],
                reasons=context["reasons"],
            ))
            return True
        except Exception:
            logger.exception("Failed to journal AI-assisted decision")
            return False

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
