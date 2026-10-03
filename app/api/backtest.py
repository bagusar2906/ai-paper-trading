from threading import Thread
import logging

from fastapi import APIRouter

from app.backtest.job_manager import job_manager
from app.backtest.backtest_request import BacktestRequest
from app.backtest.backtest_service import BacktestService

router = APIRouter(
    prefix="/backtest",
    tags=["Backtest"],
)

logger = logging.getLogger(__name__)


@router.post("")
def run_backtest(request: BacktestRequest):

    service = BacktestService()

    return service.run(request)

@router.post("/start")
def start_backtest(request: BacktestRequest):

    job_id = job_manager.create()

    Thread(
        target=_run_job,
        args=(job_id, request),
        daemon=True,
    ).start()

    return {
        "jobId": job_id,
    }

@router.get("/progress/{job_id}")
def progress(job_id: str):

    return job_manager.get(job_id)



def _run_job(
    job_id,
    request,
):

    service = BacktestService()

    print("Starting BacktestService.run()")

    try:

        result = service.run(
            request,
            job_id,
        )

        job_manager.complete(
            job_id,
            result,
        )

        print("job_manager.complete() called")

    except Exception as exc:

        logger.exception("Backtest job %s failed", job_id)
        job_manager.fail(job_id, exc)
