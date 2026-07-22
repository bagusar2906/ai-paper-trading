from threading import Thread

from fastapi import APIRouter

from app.backtest.job_manager import job_manager
from app.backtest.backtest_request import BacktestRequest
from app.backtest.backtest_service import BacktestService

router = APIRouter(
    prefix="/backtest",
    tags=["Backtest"],
)


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

    result = service.run(
        request,
        job_id,
    )

    job_manager.complete(
        job_id,
        result,
    )