from dataclasses import dataclass


from app.backtest.backtest_marker import BacktestMarker
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

    markers: list[BacktestMarker]

    stopped: bool = False

    comparison: dict | None = None

    # Used only while building a candidate comparison diagnostic. It is cleared
    # before the response leaves BacktestService, so per-candle decisions are
    # never returned to the dashboard.
    decision_trace: list[dict] | None = None
