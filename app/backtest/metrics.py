"""Cost-aware metrics calculated from a backtest equity curve."""

import math


def maximum_drawdown(equity_points) -> float:
    peak = float("-inf")
    drawdown = 0.0
    for point in equity_points:
        peak = max(peak, point.equity)
        drawdown = max(drawdown, peak - point.equity)
    return drawdown


def sharpe_ratio(equity_points, periods_per_year: int) -> float:
    """Zero-risk-rate Sharpe; caller must document the annualization period."""
    values = [point.equity for point in equity_points]
    if len(values) < 3 or periods_per_year <= 0:
        return 0.0
    returns = [next_value / value - 1 for value, next_value in zip(values, values[1:]) if value]
    if len(returns) < 2:
        return 0.0
    mean_return = sum(returns) / len(returns)
    variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
    if variance == 0:
        return 0.0
    return mean_return / math.sqrt(variance) * math.sqrt(periods_per_year)
