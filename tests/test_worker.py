from unittest.mock import patch

from app.workers.trading_worker import TradingWorker


def test_worker_run_once():

    worker = TradingWorker()

    try:
        result = worker.run_once()

        assert result is not None

    finally:
        worker.close()


def test_worker_closes_previous_engine_before_reloading():

    class Engine:

        def __init__(self):
            self.closed = False

        def run_once(self):
            return "completed"

        def close(self):
            self.closed = True

    first_engine = Engine()
    second_engine = Engine()

    with patch(
        "app.workers.trading_worker.create_engine",
        side_effect=[first_engine, second_engine],
    ):
        worker = TradingWorker()

        assert worker.run_once() == "completed"
        assert worker.run_once() == "completed"

    assert first_engine.closed

    worker.close()

    assert second_engine.closed
