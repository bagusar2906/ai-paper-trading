from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import engine


# Default session used by the application
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def create_session_factory(database_url: str):
    """
    Create an isolated Session factory for another database
    (e.g. backtesting).
    """

    backtest_engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )

    Session = sessionmaker(
        bind=backtest_engine,
        autoflush=False,
        autocommit=False,
    )

    return backtest_engine, Session