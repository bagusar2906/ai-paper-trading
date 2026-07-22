from dataclasses import dataclass, field
import datetime

from app.analytics.statistics import TradingStatistics
from app.backtest.equity_point import EquityPoint
from app.models.trade import Trade
    
@dataclass
class BacktestResult:

    statistics: TradingStatistics

    trades: list[Trade]

    equity_curve: list[EquityPoint]

    start_balance: float

    end_balance: float

    bars_processed: int