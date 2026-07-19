from app.database.database import init_database
from app.workers.trading_worker import TradingWorker


def test_worker_run_once():

    init_database()

    worker = TradingWorker()

    result = worker.run_once()

    assert result is not None