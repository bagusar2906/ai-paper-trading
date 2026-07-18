from abc import ABC, abstractmethod

from app.models.signal import TradingSignal
from app.models.position import Position
from app.models.account import Account


class Broker(ABC):

    @abstractmethod
    def execute(self, signal: TradingSignal):
        pass

    @abstractmethod
    def close_position(self, symbol: str, price: float):
        pass

    @abstractmethod
    def get_positions(self) -> list[Position]:
        pass

    @abstractmethod
    def get_account(self) -> Account:
        pass