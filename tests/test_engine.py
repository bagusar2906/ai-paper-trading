from app.engine.factory import create_engine


def test_run_engine():

    engine = create_engine()

    result = engine.run_once()

    print(result)