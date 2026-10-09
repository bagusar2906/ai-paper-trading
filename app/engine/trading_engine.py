import logging

from app.engine.result import EngineResult
from app.enums.trading_mode import TradingMode
from app.enums.signal_action import SignalAction
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
        resume_pending=False,
    ):
        self.provider = provider
        self.strategy = strategy
        self.broker = broker

        self.symbol = symbol
        self.timeframe = getattr(strategy, "required_timeframe", timeframe)
        self.bars = max(bars, strategy.minimum_bars + 1) if getattr(strategy, "next_open_execution", False) else bars
        bind_broker = getattr(strategy, "bind_broker", None)
        if bind_broker is not None:
            bind_broker(broker)

        self.respect_trading_mode = respect_trading_mode
        self.resume_pending = resume_pending

        self.equity_history = []

        self.position_manager = PositionManager(self.broker)
        self.risk_manager = RiskManager()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run_once(self, df=None):

        if df is None and self.resume_pending:
            from app.services.trading_recovery_service import TradingRecoveryService

            return TradingRecoveryService(self).run()

        #
        # Load market data
        #
        if df is None:
            df = self._load_data()

        if getattr(self.strategy, "next_open_execution", False):
            return self._run_next_open(df)

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

    def _generate_signal(self, df, execution_price=None, execution_time=None):

        signal = self.strategy.generate_signal(
            self.symbol,
            df,
        )

        if signal is None:
            return None
        if execution_price is not None:
            offset = execution_price - signal.price
            if signal.stop_loss is not None:
                signal.stop_loss += offset
            if signal.take_profit is not None:
                signal.take_profit += offset
            signal.price = execution_price
            signal.time = execution_time

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

                signal.execution_diagnostic = {"executed": False, "reason": "Trading mode is not AUTO"}

                self._journal_ai_decision(signal, context, "not_auto")

                logger.debug(
                    "Trading mode is %s - signal recorded, "
                    "not auto-executing",
                    mode,
                )

                return

        account = self.get_account()

        positions = self.broker.get_positions()

        if signal.action == SignalAction.CLOSE:
            trade = self.broker.close_position(signal.symbol, signal.price)
            signal.execution_diagnostic = {"executed": trade is not None, "reason": "Close position"}
            return trade

        # The Sol agent uses buy/sell to reverse an opposite position. Check
        # entry risk before closing; other strategies retain their old behavior.
        reversal = next((p for p in positions if p.symbol == signal.symbol and p.side != signal.action), None)
        if not getattr(self.strategy, "next_open_execution", False):
            reversal = None
        evaluated_positions = [p for p in positions if p is not reversal]

        decision = self.risk_manager.evaluate(
            signal,
            account,
            evaluated_positions,
        )

        if not decision.allowed:

            signal.execution_diagnostic = {"executed": False, "reason": decision.reason}

            self._journal_ai_decision(signal, context, "rejected")

            logger.info(
                "Trade rejected: %s",
                decision.reason,
            )

            return

        if not self._journal_ai_decision(signal, context, "approved"):
            signal.execution_diagnostic = {"executed": False, "reason": "Decision journal failed"}
            logger.error("AI-assisted paper trade rejected because its decision could not be journaled")
            return

        signal.quantity = decision.quantity

        closed = None
        if reversal is not None:
            closed = self.broker.close_position(signal.symbol, signal.price)

        logger.info(
            "Executing %s %.2f lot(s)",
            signal.action,
            signal.quantity,
        )

        self.broker.execute(signal)
        signal.execution_diagnostic = {"executed": True, "reason": "Submitted to broker"}
        return closed

    def _run_next_open(self, df):
        """Evaluate only the preceding closed candle, then fill at this open.

        No in-memory pending order is needed: recovery replays each execution
        candle atomically with its checkpoint, including after a worker restart.
        The agent never sees this candle's high, low or close before execution.
        """
        visible = df.iloc[:-1]
        if not self.strategy.can_run(visible):
            return EngineResult(account=self.get_account(), message="Not enough data")
        stamp = df.index[-1]
        opening = self._get_current_open(df)
        self.broker.simulation_time = stamp.to_pydatetime()
        advance = getattr(self.broker, "advance_candle", None)
        if advance is not None:
            advance(self.symbol, opening, stamp)
        self.broker.update_market_price(self.symbol, self._get_current_price(visible))
        signal = self._generate_signal(self.strategy.prepare(visible), opening, stamp)
        self.broker.update_market_price(self.symbol, opening)
        closed = []
        trade = self._execute_signal(signal)
        if trade is not None:
            closed.append(trade)
        # Cost-aware brokers normally queue orders; this decision was made on
        # the preceding candle, so this very open is already its next open.
        if advance is not None:
            advance(self.symbol, opening, stamp)
        # Monitor ATR stops/targets on every hourly bar, even off cadence.
        row = df.iloc[-1]
        for position in list(self.broker.get_positions()):
            if position.symbol != self.symbol:
                continue
            buy = position.side == "BUY"
            stop, target = position.stop_loss, position.take_profit
            stop_hit = stop is not None and (row["Low"] <= stop if buy else row["High"] >= stop)
            target_hit = target is not None and (row["High"] >= target if buy else row["Low"] <= target)
            if stop_hit or target_hit:
                # Stop wins if both occur in one bar; adverse gaps fill at open.
                price = (min(opening, stop) if buy else max(opening, stop)) if stop_hit else target
                trade = self.broker.close_position(self.symbol, float(price))
                if trade is not None:
                    closed.append(trade)
        self.broker.update_market_price(self.symbol, self._get_current_price(df))
        self.equity_history.append({"time": stamp, "equity": self.get_account().equity})
        return self._build_result(signal, closed)

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
