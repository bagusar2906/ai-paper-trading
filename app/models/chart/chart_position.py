from dataclasses import dataclass


@dataclass
class ChartPosition:

    symbol: str

    side: str

    entry: float

    stop_loss: float

    take_profit: float