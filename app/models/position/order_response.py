from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderResponse:

    success: bool

    message: str

    order_id: Optional[int] = None

    position_id: Optional[int] = None

    symbol: Optional[str] = None

    action: Optional[str] = None

    quantity: Optional[float] = None

    price: Optional[float] = None

    stop_loss: Optional[float] = None

    take_profit: Optional[float] = None