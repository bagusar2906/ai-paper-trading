from pydantic import BaseModel


class StrategyResponse(BaseModel):

    id: int

    name: str

    description: str

    strategy_type: str

    config_json: str

    class Config:

        from_attributes = True