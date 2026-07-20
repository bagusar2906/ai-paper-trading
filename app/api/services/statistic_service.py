from app.models.dashboard.dashboard_statistics import (
    DashboardStatistics,
)


class StatisticsService:

    def build(
        self,
        trades,
    ) -> DashboardStatistics:

        total_trades = len(trades)

        winning_trades = sum(
            1
            for trade in trades
            if trade.pnl > 0
        )

        losing_trades = sum(
            1
            for trade in trades
            if trade.pnl < 0
        )

        total_profit = sum(
            trade.pnl
            for trade in trades
            if trade.pnl > 0
        )

        total_loss = sum(
            trade.pnl
            for trade in trades
            if trade.pnl < 0
        )

        net_profit = (
            total_profit
            + total_loss
        )

        win_rate = (
            winning_trades / total_trades * 100
            if total_trades > 0
            else 0
        )

        return DashboardStatistics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=round(win_rate, 2),
            total_profit=round(total_profit, 2),
            total_loss=round(total_loss, 2),
            net_profit=round(net_profit, 2),
        )