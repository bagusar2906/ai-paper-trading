from sqlalchemy.orm import sessionmaker

from app.database.database import engine

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def create_session_factory(bind_engine):
    """Build a sessionmaker bound to an arbitrary engine (e.g. an isolated
    in-memory DB for backtesting) rather than the live database."""
    return sessionmaker(
        bind=bind_engine,
        autoflush=False,
        autocommit=False,
    )