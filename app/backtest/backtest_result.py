from dataclasses import dataclass, field
import datetime

from app.analytics.statistics import TradingStatistics
from app.backtest.equity_point import EquityPoint
from app.models.trade import Trade
from app.backtest.costs import CostBreakdown
    
@dataclass
class BacktestResult:

    statistics: TradingStatistics

    trades: list[Trade]

    equity_curve: list[EquityPoint]

    start_balance: float

    end_balance: float

    bars_processed: int

    max_drawdown: float = 0.0

    sharpe_ratio: float = 0.0

    periods_per_year: int = 0

    cost_breakdown: CostBreakdown | None = None

    fill_timing: str = "current_candle_close"
