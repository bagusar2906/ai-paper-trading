from dataclasses import dataclass


@dataclass
class PositionResponse:

    symbol: str

    side: str

    quantity: float

    entry_price: float

    current_price: float

    stop_loss: float

    take_profit: float

    floating_pnl: float