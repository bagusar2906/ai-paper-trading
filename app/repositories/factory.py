from app.database import SessionLocal

from app.repositories.account_repository import AccountRepository
from app.repositories.position_repository import PositionRepository
from app.repositories.trade_repository import TradeRepository
from app.repositories.signal_repository import SignalRepository


class RepositoryFactory:

    def __init__(self):

        self.session = SessionLocal()

        self.accounts = AccountRepository(self.session)
        self.positions = PositionRepository(self.session)
        self.trades = TradeRepository(self.session)
        self.signals = SignalRepository(self.session)

    def close(self):

        self.session.close()