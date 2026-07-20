from fastapi import APIRouter

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
