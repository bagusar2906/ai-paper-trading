from app.brokers.base import Broker
from app.models.account import Account
from app.models.position import Position
from app.models.signal import TradingSignal


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

    def execute(self, signal: TradingSignal):

        if signal.action not in ("BUY", "SELL"):
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

    def close_position(self, symbol: str, price: float):
        raise NotImplementedError("Will implement in Version 2")

    def get_positions(self) -> list[Position]:
        return self._positions

    def get_account(self) -> Account:
        return self._account