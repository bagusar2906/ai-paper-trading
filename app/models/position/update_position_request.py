from dataclasses import dataclass


@dataclass
class UpdatePositionRequest:

    stop_loss: float

    take_profit: float