from dataclasses import dataclass


@dataclass
class StrategyProfile:

    id: int | None = None

    name: str = ""

    strategy_id: int = 0

    symbol: str = ""

    timeframe: str = ""

    bars: int = 5000

    initial_balance: float = 10000