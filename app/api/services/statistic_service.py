from app.models.dashboard.dashboard_statistics import (
    DashboardStatistics,
)


class StatisticsService:

    def build(
        self,
        trades,
        max_drawdown: float = 0,
    ) -> DashboardStatistics:

        total_trades = len(trades)

        winning = [
            trade
            for trade in trades
            if trade.pnl > 0
        ]

        losing = [
            trade
            for trade in trades
            if trade.pnl < 0
        ]

        winning_trades = len(winning)

        losing_trades = len(losing)

        total_profit = sum(
            trade.pnl
            for trade in winning
        )

        total_loss = sum(
            trade.pnl
            for trade in losing
        )

        net_profit = (
            total_profit
            + total_loss
        )

        win_rate = (
            winning_trades
            / total_trades
            * 100
            if total_trades > 0
            else 0
        )

        gross_loss = abs(total_loss)

        profit_factor = (
            total_profit / gross_loss
            if gross_loss > 0
            else 0
        )

        average_win = (
            total_profit / winning_trades
            if winning_trades > 0
            else 0
        )

        average_loss = (
            gross_loss / losing_trades
            if losing_trades > 0
            else 0
        )

        largest_win = max(
            (trade.pnl for trade in winning),
            default=0,
        )

        largest_loss = min(
            (trade.pnl for trade in losing),
            default=0,
        )

        win_probability = (
            winning_trades / total_trades
            if total_trades > 0
            else 0
        )

        loss_probability = (
            losing_trades / total_trades
            if total_trades > 0
            else 0
        )

        expectancy = (
            win_probability * average_win
            - loss_probability * average_loss
        )

        return DashboardStatistics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=round(win_rate, 2),
            total_profit=round(total_profit, 2),
            total_loss=round(total_loss, 2),
            net_profit=round(net_profit, 2),
            profit_factor=round(
                profit_factor,
                2,
            ),
            average_win=round(
                average_win,
                2,
            ),
            average_loss=round(
                average_loss,
                2,
            ),
            largest_win=round(
                largest_win,
                2,
            ),
            largest_loss=round(
                largest_loss,
                2,
            ),
            max_drawdown=round(
                max_drawdown,
                2,
            ),
            win_probability=round(win_probability, 2),
            loss_probability=round(loss_probability, 2),
            expectancy=round(expectancy, 2),
        )