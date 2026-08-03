from pydantic import BaseModel


class StrategyParameter(BaseModel):

    key: str

    label: str

    type: str

    default: object

    minimum: float | None = None

    maximum: float | None = None

    step: float | None = None