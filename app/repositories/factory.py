from sqlalchemy.orm import sessionmaker

from app.database import SessionLocal

from app.repositories.account_repository import AccountRepository
from app.repositories.position_repository import PositionRepository
from app.repositories.trade_repository import TradeRepository
from app.repositories.signal_repository import SignalRepository


class RepositoryFactory:

    def __init__(
        self,
        session=None,
        session_factory: sessionmaker | None = None,
    ):

        if session is not None:

            self.session = session

        else:

            self.session = (
                session_factory or SessionLocal
            )()

        self.accounts = AccountRepository(self.session)
        self.positions = PositionRepository(self.session)
        self.trades = TradeRepository(self.session)
        self.signals = SignalRepository(self.session)

    def close(self):

        self.session.close()