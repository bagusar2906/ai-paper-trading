from datetime import datetime

from app.brokers.base import Broker
from app.enums.signal_action import SignalAction
from app.models.account import Account
from app.models.position import Position
from app.models.signal import TradingSignal
from app.models.trade import Trade


class BacktestBroker(Broker):

    def __init__(self, initial_balance=10000):

        self.account = Account(
            balance=initial_balance,
            equity=initial_balance,
            margin=0,
            free_margin=initial_balance,
            floating_pnl=0,
        )

        self.positions = []

        self.trades = []

    # -------------------------------------

    def execute(self, signal: TradingSignal):

        if signal.action not in (
            SignalAction.BUY,
            SignalAction.SELL,
        ):
            return

        #
        # only one position per symbol
        #

        for p in self.positions:

            if p.symbol == signal.symbol:
                return

        position = Position(
            id=len(self.positions) + 1,
            symbol=signal.symbol,
            side=signal.action,
            quantity=signal.quantity,
            entry_price=signal.price,
            current_price=signal.price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            floating_pnl=0,
            opened_at=signal.time,
        )

        self.positions.append(position)

    def close_position(
            self,
            symbol,
            price,
        ):

        position = next(
            (
                p
                for p in self.positions
                if p.symbol == symbol
            ),
            None,
        )

        if position is None:
            return

        if position.side == SignalAction.BUY:

            pnl = (
                price
                - position.entry_price
            ) * position.quantity

        else:

            pnl = (
                position.entry_price
                - price
            ) * position.quantity

        trade = Trade(
            symbol=position.symbol,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=price,
            pnl=pnl,
            opened_at=position.opened_at,
            closed_at=datetime.now(),
        )

        self.trades.append(trade)

        self.positions.remove(position)

        self.account.balance += pnl

        self.account.equity = self.account.balance

        self.account.free_margin = self.account.balance

        return trade
    
    def update_market_price(
            self,
            symbol,
            current_price,
        ):

        floating = 0

        for position in self.positions:

            if position.symbol != symbol:
                continue

            position.current_price = current_price

            if position.side == SignalAction.BUY:

                pnl = (
                    current_price
                    - position.entry_price
                ) * position.quantity

            else:

                pnl = (
                    position.entry_price
                    - current_price
                ) * position.quantity

            position.floating_pnl = pnl

            floating += pnl

        self.account.floating_pnl = floating

        self.account.equity = (
            self.account.balance
            + floating
        )

        self.account.free_margin = (
            self.account.equity
            - self.account.margin
        )

    def get_positions(self):

        return self.positions


    def get_trades(self):

        return self.trades


    def get_account(self):

        return self.account


    def close(self):

        pass