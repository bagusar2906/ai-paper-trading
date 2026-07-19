from dataclasses import dataclass


@dataclass
class TradingStatistics:

    total_trades: int = 0

    winning_trades: int = 0

    losing_trades: int = 0

    breakeven_trades: int = 0

    gross_profit: float = 0.0

    gross_loss: float = 0.0

    net_profit: float = 0.0

    win_rate: float = 0.0

    profit_factor: float = 0.0

    average_win: float = 0.0

    average_loss: float = 0.0

    largest_win: float = 0.0

    largest_loss: float = 0.0