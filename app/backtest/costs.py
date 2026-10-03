"""Explicit fill and transaction-cost assumptions for offline backtests."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestCostAssumptions:
    """Costs expressed in instrument price units, per traded unit.

    A strategy decides at a completed candle close. Orders are filled at the
    next candle open; full spread is split evenly across entry and exit.
    """

    spread_price: float = 0.0
    slippage_price: float = 0.0
    commission_per_unit_per_side: float = 0.0
    fill_timing: str = "next_candle_open"

    def __post_init__(self):
        if self.fill_timing != "next_candle_open":
            raise ValueError("only next_candle_open timing is supported")
        if any(value < 0 for value in (
            self.spread_price,
            self.slippage_price,
            self.commission_per_unit_per_side,
        )):
            raise ValueError("backtest cost assumptions cannot be negative")


@dataclass(frozen=True)
class CostBreakdown:
    spread_cost: float = 0.0
    slippage_cost: float = 0.0
    commission_cost: float = 0.0

    @property
    def total_cost(self) -> float:
        return self.spread_cost + self.slippage_cost + self.commission_cost
