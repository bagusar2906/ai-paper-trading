from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChartMarker:

    time: datetime

    position: str

    color: str

    shape: str

    text: str