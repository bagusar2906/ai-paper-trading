from dataclasses import dataclass


from app.backtest.equity_point import EquityPoint
from app.models.dashboard.dashboard_statistics import DashboardStatistics
from app.models.trade import Trade


@dataclass
class BacktestResponse:

    statistics: DashboardStatistics

    equity: list[EquityPoint]

    trades: list[Trade]

    candles: list[dict]

    ema: list[dict]

    rsi: list[dict]

    adx: list[dict]