from dataclasses import dataclass


@dataclass
class BacktestRequest:

    strategy_id: int

    symbol: str

    timeframe: str

    bars: int = 5000

    initial_balance: float = 10000

    # Supplying a candidate asks for an offline-only comparison. It never
    # changes the champion and is rejected for non-AI-assisted strategies.
    candidate_model_id: str | None = None
