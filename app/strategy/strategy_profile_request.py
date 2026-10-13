from pydantic import BaseModel


class StrategyProfileRequest(BaseModel):

    name: str

    strategy_id: int

    symbol: str

    timeframe: str

    bars: int

    initial_balance: float