from dataclasses import dataclass
from datetime import datetime


@dataclass
class LinePoint:

    time: datetime

    value: float