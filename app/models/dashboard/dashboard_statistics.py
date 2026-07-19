from dataclasses import dataclass


@dataclass
class DashboardStatistics:

    total_trades: int

    winning_trades: int

    losing_trades: int

    win_rate: float

    total_profit: float

    total_loss: float

    net_profit: float