from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Trade:

    id: Optional[int]

    symbol: str

    side: str

    quantity: float

    entry_price: float

    exit_price: float

    pnl: float

    opened_at: datetime

    closed_at: Optional[datetime]