from contextlib import contextmanager

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
from app.repositories.model_registry_repository import ModelRegistryRepository
from app.repositories.trading_checkpoint_repository import TradingCheckpointRepository



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
        self.model_registry = ModelRegistryRepository(self.session)
        self.trading_checkpoints = TradingCheckpointRepository(self.session)

    @contextmanager
    def trading_transaction(self):
        """Commit account, trades, signals and the resume point together.

        SQLite's writer lock is acquired before reading the checkpoint, so
        overlapping scheduler/worker processes cannot execute a candle twice.
        """
        if self.session.info.get("paper_trading_transaction"):
            raise RuntimeError("A trading transaction is already active")
        if self.session.new or self.session.dirty or self.session.deleted:
            raise RuntimeError("Cannot start recovery with pending database writes")
        # End the read transaction left by loading the account/configuration.
        self.session.rollback()
        try:
            connection = self.session.connection()
            if connection.dialect.name == "sqlite":
                connection.exec_driver_sql("BEGIN IMMEDIATE")
            self.session.info["paper_trading_transaction"] = True
            yield
            self.session.commit()
        except BaseException:
            self.session.rollback()
            raise
        finally:
            self.session.info.pop("paper_trading_transaction", None)

    def close(self):

        self.session.close()
