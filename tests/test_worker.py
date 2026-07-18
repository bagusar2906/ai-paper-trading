from app.workers.trading_worker import TradingWorker
from app.engine.result import EngineResult


def test_worker_run_once():

    worker = TradingWorker()

    result = worker.run_once()

    assert isinstance(result, EngineResult)
    assert result.account is not None