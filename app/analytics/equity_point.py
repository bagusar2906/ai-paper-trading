from dataclasses import dataclass
from datetime import datetime


@dataclass
class EquityPoint:

    time: datetime
    balance: float
    equity: float