import pytest

from app.database import Base, engine
from app.database.database import init_database


@pytest.fixture(autouse=True)
def database():

    Base.metadata.drop_all(bind=engine)
    init_database()

    yield

    Base.metadata.drop_all(bind=engine)