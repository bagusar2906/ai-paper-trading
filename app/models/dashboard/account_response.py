from pydantic import BaseModel


class AccountResponse(BaseModel):

    balance: float
    equity: float
    margin: float
    free_margin: float
    floating_pnl: float