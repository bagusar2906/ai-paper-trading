from attr import dataclass


@dataclass
class OrderRequest:

    symbol: str

    action: str

    price: float

    quantity: float

    stop_loss: float

    take_profit: float