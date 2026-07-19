import os

from app.database import SessionLocal
from app.database import Base
from app.database import engine

from app.database.models import PositionEntity
from app.repositories.position_repository import PositionRepository


def setup_module():

    # Start each test with a clean database
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module():

    Base.metadata.drop_all(bind=engine)


def test_position_repository():

    session = SessionLocal()

    repo = PositionRepository(session)

    position = PositionEntity(
        symbol="XAUUSD",
        side="BUY",
        quantity=1,
        entry_price=3350.0,
        stop_loss=3340.0,
        take_profit=3370.0,
        opened_at=None,
    )

    repo.add(position)

    positions = repo.get_all()

    assert len(positions) == 1

    assert positions[0].symbol == "XAUUSD"

    assert positions[0].side == "BUY"

    repo.remove(position)

    positions = repo.get_all()

    assert len(positions) == 0

    session.close()