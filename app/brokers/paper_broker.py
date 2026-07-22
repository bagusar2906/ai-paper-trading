from datetime import datetime
import logging

from app.brokers.base import Broker
from app.database.models import (
    AccountEntity,
    PositionEntity,
    TradeEntity,
)
from app.enums.signal_action import SignalAction
from app.models.account import Account
from app.models.signal import TradingSignal
from app.repositories.factory import RepositoryFactory

logger = logging.getLogger(__name__)


class PaperBroker(Broker):

    def __init__(
            self,
            repos: RepositoryFactory = None,
            initial_balance: float = 10000,
        ):

        self.initial_balance = initial_balance
        self.repos = repos or RepositoryFactory()

        account = self.repos.accounts.get()

        if account is None:

            account = Account(
                balance=self.initial_balance,
                equity=self.initial_balance,
                margin=0,
                free_margin=self.initial_balance,
                floating_pnl=0,
            )

            self.repos.accounts.add(account)

        self._account = account

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

        existing = self.repos.positions.get_by_symbol(
            signal.symbol
        )

        if existing is not None:

            logger.info(
                "Position already exists for %s",
                signal.symbol,
            )

            return

        entity = PositionEntity(
            symbol=signal.symbol,
            side=signal.action,
            quantity=signal.quantity or 1.0,
            entry_price=signal.price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            opened_at=signal.time,
        )

        self.repos.positions.add(entity)

        logger.info(
            "Opened %s %.2f %s @ %.2f",
            entity.side,
            entity.quantity,
            entity.symbol,
            entity.entry_price,
        )

    def close_position(
        self,
        symbol: str,
        price: float,
    ):

        position = self.repos.positions.get_by_symbol(symbol)

        if position is None:
            return None

        if position.side == SignalAction.BUY:

            pnl = (
                price - position.entry_price
            ) * position.quantity

        else:

            pnl = (
                position.entry_price - price
            ) * position.quantity

        trade = TradeEntity(
            symbol=position.symbol,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=price,
            pnl=pnl,
            opened_at=position.opened_at,
            closed_at=datetime.now(),
        )

        self.repos.trades.add(trade)

        self.repos.positions.remove(position)

        self._account.balance += pnl
        self._account.equity = self._account.balance
        self._account.free_margin = self._account.balance

        self.repos.accounts.update(self._account)

        logger.info(
            "Closed %s %s @ %.2f | P/L %.2f | Balance %.2f",
            position.side,
            position.symbol,
            price,
            pnl,
            self._account.balance,
        )

        return trade

    def get_positions(self):

        return self.repos.positions.get_all()

    def get_trades(self):

        return self.repos.trades.get_all()

    def get_account(self):

        return self.repos.accounts.get()
    
    def close(self):

        self.repos.close()

    def update_market_price(
        self,
        symbol: str,
        current_price: float,
        ):

        positions = self.repos.positions.get_all()

        account = self.repos.accounts.get()

        floating = 0

        for position in positions:

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

            position.profit = pnl

            floating += pnl

            self.repos.positions.update(position)

        account.floating_pnl = floating
        account.equity = account.balance + floating
        account.free_margin = account.equity - account.margin

        self.repos.accounts.update(account)

    def save_signal(self, signal):

        self.repos.signals.add(signal)

        self.repos.session.commit()

    def get_trading_mode(self):

        return self.repos.settings.get_trading_mode()
    

    def process_signal(self, signal):

        self.repos.signals.add(signal)

        self.repos.session.commit()

        mode = self.repos.settings.get_trading_mode()

        if mode == "AUTO":

            self.execute(signal)