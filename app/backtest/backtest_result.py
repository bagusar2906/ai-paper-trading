from dataclasses import dataclass, field

from app.analytics.statistics import TradingStatistics
from app.models.trade import Trade


@dataclass
class BacktestResult:

    statistics: TradingStatistics

    trades: list[Trade] = field(default_factory=list)

    start_balance: float = 0.0

    end_balance: float = 0.0

    bars_processed: int = 0