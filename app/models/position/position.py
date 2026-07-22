from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:

    id: int

    symbol: str

    side: str

    quantity: float

    entry_price: float

    current_price: float | None = None

    floating_pnl: float = 0

    stop_loss: float | None = None

    take_profit: float | None = None

    opened_at: datetime | None = None