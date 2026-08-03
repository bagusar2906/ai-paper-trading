from pydantic import BaseModel


class StrategyRequest(BaseModel):

    name: str

    description: str

    strategy_type: str

    config: str