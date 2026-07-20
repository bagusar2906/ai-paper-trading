from dataclasses import dataclass


@dataclass
class AccountSnapshot:
    balance: float
    equity: float
    margin: float
    free_margin: float