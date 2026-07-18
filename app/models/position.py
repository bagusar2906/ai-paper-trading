from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Position:

    id: Optional[int]

    symbol: str

    side: str          # BUY / SELL

    quantity: float

    entry_price: float

    stop_loss: Optional[float]

    take_profit: Optional[float]

    opened_at: datetime