from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from app.models.fund_adjustment_request import FundAdjustmentRequest
from app.services.account_service import AccountService


router = APIRouter()


@router.post("/account/funds")
def adjust_funds(request: FundAdjustmentRequest):

    try:
        account = AccountService().adjust_funds(request.amount)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return asdict(account)
