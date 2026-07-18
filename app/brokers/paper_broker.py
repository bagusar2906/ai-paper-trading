from datetime import datetime

from app.brokers.base import Broker
from app.enums.signal_action import SignalAction
from app.models.account import Account
from app.models.position import Position
from app.models.signal import TradingSignal
from app.models.trade import Trade
import logging

logger = logging.getLogger(__name__)


class PaperBroker(Broker):

    def __init__(self, initial_balance: float = 10_000):

        self._account = Account(
            balance=initial_balance,
            equity=initial_balance,
            margin=0.0,
            free_margin=initial_balance,
            floating_pnl=0.0,
        )

        self._positions: list[Position] = []
        self._trades: list[Trade] = []

    def execute(self, signal: TradingSignal):

        if signal.action not in (
            SignalAction.BUY,
            SignalAction.SELL,
        ):
            logger.info(
                "Ignoring %s signal for %s",
                signal.action,
                signal.symbol,
            )
            return

        if any(p.symbol == signal.symbol for p in self._positions):
            logger.info(
                "Position already exists for %s. Ignoring signal.",
                signal.symbol,
            )

            return

        position = Position(
            id=None,
            symbol=signal.symbol,
            side=signal.action,
            quantity=1.0,
            entry_price=signal.price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            opened_at=signal.time,
        )

        self._positions.append(position)

        logger.info(
            "Opened %s %s @ %.2f (SL=%.2f TP=%.2f)",
            position.side,
            position.symbol,
            position.entry_price,
            position.stop_loss,
            position.take_profit,
        )

    def close_position(self, symbol: str, price: float):

        position = next(
            (p for p in self._positions if p.symbol == symbol),
            None
        )

        if position is None:
            return None

        if position.side == SignalAction.BUY:
            pnl = (price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - price) * position.quantity

        trade = Trade(
            id=None,
            symbol=position.symbol,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=price,
            pnl=pnl,
            opened_at=position.opened_at,
            closed_at=datetime.now(),
        )

        self._trades.append(trade)

        self._positions.remove(position)

        self._account.balance += pnl
        self._account.equity = self._account.balance
        self._account.free_margin = self._account.balance
        
        logger.info(
            "Closed %s %s @ %.2f | P/L = %.2f | Balance = %.2f",
            position.side,
            symbol,
            price,
            pnl,
            self._account.balance,
        )

        return trade

    def get_positions(self):

        return self._positions

    def get_trades(self):

        return self._trades

    def get_account(self):

        return self._account