from app.database import engine


def test_database_created():

    assert engine is not None