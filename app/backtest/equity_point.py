from dataclasses import dataclass
from datetime import datetime


@dataclass
class EquityPoint:

    time: datetime

    equity: float