from dataclasses import dataclass

from app.models.account import Account
from app.models.position import Position
from app.models.signal import TradingSignal
from app.models.trade import Trade

from .dashboard_statistics import DashboardStatistics
from .active_strategy_response import ActiveStrategyResponse


@dataclass
class DashboardResponse:

    account: Account

    current_signal: TradingSignal | None

    positions: list[Position]

    trades: list[Trade]

    signals: list[TradingSignal]

    statistics: DashboardStatistics

    active_strategy: ActiveStrategyResponse | None

    # Current application setting, not a historical attribute of a position.
    trading_mode: str
