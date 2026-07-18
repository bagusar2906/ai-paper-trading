from dataclasses import dataclass


@dataclass
class Account:

    balance: float

    equity: float

    margin: float

    free_margin: float

    floating_pnl: float