from dataclasses import dataclass


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

    profit_factor: float

    average_win: float

    average_loss: float

    largest_win: float

    largest_loss: float

    max_drawdown: float

    win_probability: float

    loss_probability: float

    expectancy: float