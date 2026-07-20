from dataclasses import dataclass

from app.models.trade import Trade
from app.models.dashboard.dashboard_statistics import DashboardStatistics

from .equity_point import EquityPoint


@dataclass
class BacktestResponse:

    statistics: DashboardStatistics

    equity: list[EquityPoint]

    trades: list[Trade]