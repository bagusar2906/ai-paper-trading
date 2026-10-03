from sqlalchemy.orm import sessionmaker

from app.database import SessionLocal

from app.repositories.account_repository import AccountRepository
from app.repositories.position_repository import PositionRepository
from app.repositories.settings_repository import SettingsRepository
from app.repositories.trade_repository import TradeRepository
from app.repositories.signal_repository import SignalRepository
from app.repositories.strategy_repository import StrategyRepository
from app.repositories.market_candle_repository import MarketCandleRepository
from app.repositories.data_quality_event_repository import DataQualityEventRepository
from app.repositories.decision_journal_repository import DecisionJournalRepository



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
        self.settings = SettingsRepository(self.session)
        self.strategies = StrategyRepository(self.session)
        self.market_candles = MarketCandleRepository(self.session)
        self.data_quality_events = DataQualityEventRepository(self.session)
        self.decision_journal = DecisionJournalRepository(self.session)

    def close(self):

        self.session.close()
