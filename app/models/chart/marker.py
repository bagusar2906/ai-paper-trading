from dataclasses import dataclass


@dataclass
class ChartMarker:

    time: str

    position: str      # "aboveBar" | "belowBar"

    color: str

    shape: str         # "arrowUp" | "arrowDown"

    text: str