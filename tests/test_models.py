from app.database.models import (
    AccountEntity,
    PositionEntity,
    SignalEntity,
    TradeEntity,
)


def test_entities_exist():

    assert AccountEntity.__tablename__ == "accounts"

    assert PositionEntity.__tablename__ == "positions"

    assert TradeEntity.__tablename__ == "trades"

    assert SignalEntity.__tablename__ == "signals"