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