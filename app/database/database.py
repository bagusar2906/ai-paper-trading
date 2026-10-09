import os
from pathlib import Path

from sqlalchemy import create_engine

from app.database.base import Base

# IMPORTANT: import all models so SQLAlchemy knows about them
import app.database.models

DATABASE_PATH = Path(os.environ.get(
    "PAPER_TRADING_DB_PATH",
    str(Path(__file__).resolve().parents[2] / "data" / "paper_trading.db"),
)).resolve()
DATA_DIR = DATABASE_PATH.parent
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
)


def init_database():
    Base.metadata.create_all(bind=engine)


def create_isolated_engine(database_url: str = "sqlite:///:memory:"):
    """
    Build a standalone SQLAlchemy engine with its own tables, independent of
    the live paper-trading DB. Used by the backtest engine so replaying
    history never touches your real positions/trades/account.
    """
    isolated_engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(bind=isolated_engine)
    return isolated_engine