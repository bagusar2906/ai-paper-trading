from dataclasses import dataclass


@dataclass
class BacktestRequest:

    strategy_id: int

    symbol: str

    timeframe: str

    bars: int = 5000

    initial_balance: float = 10000