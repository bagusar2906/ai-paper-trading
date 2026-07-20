from dataclasses import dataclass

from app.analytics.equity_point import EquityPoint
from app.brokers.trade import Trade
from app.models.dashboard.dashboard_statistics import DashboardStatistics


@dataclass
class BacktestReport:

    statistics: DashboardStatistics

    trades: list[Trade]

    equity_curve: list[EquityPoint]

    max_drawdown: float

    profit_factor: float

    expectancy: float

    sharpe_ratio: float