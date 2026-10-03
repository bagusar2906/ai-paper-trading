from dataclasses import dataclass


@dataclass
class ActiveStrategyResponse:
    id: int
    name: str
    strategy_type: str
    stop_loss_pips: float | None = None
    take_profit_pips: float | None = None
    risk_reward_ratio: float | None = None
