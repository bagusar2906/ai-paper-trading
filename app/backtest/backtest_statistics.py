from dataclasses import dataclass


@dataclass
class BacktestStatistics:

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

    max_drawdown: float

    expectancy: float