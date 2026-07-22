print(">>> LOADED MY CONFTEST <<<")
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    
from app.database.base import Base

from app.repositories.factory import RepositoryFactory
from app.brokers.paper_broker import PaperBroker


@pytest.fixture(scope="function")
def session():

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(engine)

    Session = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    session = Session()

    yield session

    session.close()


@pytest.fixture
def repos(session):

    repos = RepositoryFactory(
        session=session
    )

    yield repos

    repos.close()


@pytest.fixture
def broker(repos):

    return PaperBroker(
        repos=repos,
        initial_balance=10000,
    )