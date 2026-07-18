from pathlib import Path

from sqlalchemy import create_engine

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'paper_trading.db'}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
)