from dataclasses import dataclass


@dataclass
class Position:

    symbol: str

    side: str

    quantity: float

    entry_price: float

    stop_loss: float

    take_profit: float

    current_price: float = 0

    profit: float = 0