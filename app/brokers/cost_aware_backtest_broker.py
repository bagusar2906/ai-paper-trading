"""Paper-only backtest broker with next-open fills and explicit costs."""

from datetime import datetime

from app.backtest.costs import BacktestCostAssumptions, CostBreakdown
from app.brokers.base import Broker
from app.enums.signal_action import SignalAction
from app.models.account import Account
from app.models.position import Position
from app.models.signal import TradingSignal
from app.models.trade import Trade


class CostAwareBacktestBroker(Broker):
    """Simulates delayed fills; it has no MT5 or live-order capability."""

    def __init__(
        self,
        initial_balance: float = 10_000,
        assumptions: BacktestCostAssumptions | None = None,
    ):
        self.initial_balance = initial_balance
        self.assumptions = assumptions or BacktestCostAssumptions()
        self.account = Account(
            balance=initial_balance,
            equity=initial_balance,
            margin=0.0,
            free_margin=initial_balance,
            floating_pnl=0.0,
        )
        self.positions: list[Position] = []
        self.trades: list[Trade] = []
        self.pending_signals: list[TradingSignal] = []
        self._market_time: datetime | None = None
        self._spread_cost = 0.0
        self._slippage_cost = 0.0
        self._commission_cost = 0.0

    def execute(self, signal: TradingSignal):
        if signal.action not in (SignalAction.BUY, SignalAction.SELL):
            return
        if any(position.symbol == signal.symbol for position in self.positions):
            return
        if any(pending.symbol == signal.symbol for pending in self.pending_signals):
            return
        self.pending_signals.append(signal)

    def advance_candle(self, symbol: str, open_price: float, candle_time: datetime):
        """Fill queued decisions at the *next* candle's open, never its close."""
        self._market_time = candle_time
        for signal in list(self.pending_signals):
            if signal.symbol != symbol:
                continue
            self.pending_signals.remove(signal)
            quantity = signal.quantity or 1.0
            fill_price = self._entry_fill_price(signal.action, open_price)
            entry_commission = self._commission(quantity)
            position = Position(
                id=len(self.positions) + 1,
                symbol=signal.symbol,
                side=signal.action,
                quantity=quantity,
                entry_price=fill_price,
                current_price=open_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                opened_at=candle_time,
            )
            # Position is an in-memory backtest model. Carrying this internal
            # value lets equity and realized P/L both include entry commission.
            position.entry_commission = entry_commission
            self.positions.append(position)
            self._record_entry_costs(quantity)

    def close_position(self, symbol: str, price: float):
        position = next((item for item in self.positions if item.symbol == symbol), None)
        if position is None:
            return None
        exit_price = self._exit_fill_price(position.side, price)
        if position.side == SignalAction.BUY:
            pnl_before_costs = (exit_price - position.entry_price) * position.quantity
        else:
            pnl_before_costs = (position.entry_price - exit_price) * position.quantity
        exit_commission = self._commission(position.quantity)
        pnl = pnl_before_costs - position.entry_commission - exit_commission
        self._record_exit_costs(position.quantity)
        trade = Trade(
            id=None,
            symbol=position.symbol,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=exit_price,
            pnl=pnl,
            opened_at=position.opened_at,
            closed_at=self._market_time or position.opened_at,
        )
        self.trades.append(trade)
        self.positions.remove(position)
        self.account.balance += pnl
        self.account.equity = self.account.balance
        self.account.free_margin = self.account.balance
        self.account.floating_pnl = 0.0
        return trade

    def update_market_price(self, symbol: str, current_price: float):
        floating = 0.0
        for position in self.positions:
            if position.symbol != symbol:
                continue
            position.current_price = current_price
            exit_price = self._exit_fill_price(position.side, current_price)
            if position.side == SignalAction.BUY:
                pnl = (exit_price - position.entry_price) * position.quantity
            else:
                pnl = (position.entry_price - exit_price) * position.quantity
            # Equity includes the entry commission already incurred and the
            # expected commission for an immediate closing fill.
            position.floating_pnl = pnl - position.entry_commission - self._commission(position.quantity)
            floating += position.floating_pnl
        self.account.floating_pnl = floating
        self.account.equity = self.account.balance + floating
        self.account.free_margin = self.account.equity - self.account.margin

    def get_positions(self) -> list[Position]:
        return self.positions

    def get_trades(self) -> list[Trade]:
        return self.trades

    def get_account(self) -> Account:
        return self.account

    def get_cost_breakdown(self) -> CostBreakdown:
        return CostBreakdown(
            spread_cost=self._spread_cost,
            slippage_cost=self._slippage_cost,
            commission_cost=self._commission_cost,
        )

    def close(self):
        pass

    def _entry_fill_price(self, action: SignalAction, price: float) -> float:
        adverse = self.assumptions.spread_price / 2 + self.assumptions.slippage_price
        return price + adverse if action == SignalAction.BUY else price - adverse

    def _exit_fill_price(self, action: SignalAction, price: float) -> float:
        adverse = self.assumptions.spread_price / 2 + self.assumptions.slippage_price
        return price - adverse if action == SignalAction.BUY else price + adverse

    def _commission(self, quantity: float) -> float:
        return self.assumptions.commission_per_unit_per_side * quantity

    def _record_entry_costs(self, quantity: float):
        self._spread_cost += self.assumptions.spread_price / 2 * quantity
        self._slippage_cost += self.assumptions.slippage_price * quantity
        self._commission_cost += self._commission(quantity)

    def _record_exit_costs(self, quantity: float):
        self._record_entry_costs(quantity)
