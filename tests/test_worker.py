from app.database.database import init_database
from app.workers.trading_worker import TradingWorker


def test_worker_run_once():

    worker = TradingWorker()

    try:
        result = worker.run_once()

        assert result is not None

    finally:
        worker.close()