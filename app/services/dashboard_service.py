from app.models.dashboard.dashboard_response import DashboardResponse
from app.models.dashboard.dashboard_statistics import DashboardStatistics
from app.repositories.factory import RepositoryFactory


class DashboardService:

    def __init__(self):

        self.repos = RepositoryFactory()

    def get_dashboard(self):

        account = self.repos.accounts.get()

        positions = self.repos.positions.get_all()

        trades = self.repos.trades.get_all()

        signals = self.repos.signals.get_recent(20)

        statistics = self._calculate_statistics(trades)

        return DashboardResponse(
            account=account,
            current_signal=signals[0] if signals else None,
            positions=positions,
            trades=trades,
            signals=signals,
            statistics=statistics,
        )

    def _calculate_statistics(self, trades):

        total = len(trades)

        wins = sum(1 for t in trades if t.pnl > 0)

        losses = sum(1 for t in trades if t.pnl < 0)

        total_profit = sum(t.pnl for t in trades if t.pnl > 0)

        total_loss = sum(t.pnl for t in trades if t.pnl < 0)

        return DashboardStatistics(
            total_trades=total,
            winning_trades=wins,
            losing_trades=losses,
            win_rate=(wins / total * 100) if total else 0,
            total_profit=total_profit,
            total_loss=total_loss,
            net_profit=total_profit + total_loss,
        )