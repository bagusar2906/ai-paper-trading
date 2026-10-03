from dataclasses import dataclass


@dataclass
class ActiveStrategyResponse:
    id: int
    name: str
    strategy_type: str
