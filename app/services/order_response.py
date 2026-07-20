from dataclasses import dataclass


@dataclass
class OrderResponse:

    success: bool

    message: str