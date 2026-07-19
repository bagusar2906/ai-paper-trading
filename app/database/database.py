from pathlib import Path

from sqlalchemy import create_engine

from app.database.base import Base

# IMPORTANT: import all models so SQLAlchemy knows about them
import app.database.models

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'paper_trading.db'}"

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