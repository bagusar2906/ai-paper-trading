from dataclasses import dataclass
from datetime import datetime


@dataclass
class SignalResponse:

    symbol: str

    action: str

    price: float

    confidence: float

    stop_loss: float

    take_profit: float

    quantity: float

    reason: str

    time: datetime

    risk_reward: float