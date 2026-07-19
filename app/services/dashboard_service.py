from app.models.dashboard.dashboard_response import DashboardResponse
from app.models.dashboard.dashboard_statistics import DashboardStatistics
from app.models.dashboard.signal_response import SignalResponse
from app.repositories.factory import RepositoryFactory


class DashboardService:

    def __init__(self):

        self.repos = RepositoryFactory()

    def get_dashboard(self):

        account = self.repos.accounts.get()
        print(f"Account: {account}")

        positions = self.repos.positions.get_all()

        trades = self.repos.trades.get_all()

        signals = self.repos.signals.get_recent(20)

        statistics = self._calculate_statistics(trades)

        current_signal = self._build_signal(
            signals[0] if signals else None
        )

        print(f"Statistics: {statistics}")

        return DashboardResponse(
            account=account,
            current_signal=current_signal,
            positions=positions,
            trades=trades,
            signals=signals,
            statistics=statistics,
        )
    
    from app.models.dashboard.signal_response import SignalResponse


    def _build_signal(
        self,
        signal,
    ) -> SignalResponse | None:

        if signal is None:
            return None

        risk_reward = 0.0

        if (
            signal.stop_loss is not None
            and signal.take_profit is not None
        ):

            risk = abs(
                signal.price - signal.stop_loss
            )

            reward = abs(
                signal.take_profit - signal.price
            )

            if risk > 0:
                risk_reward = reward / risk

        return SignalResponse(
            symbol=signal.symbol,
            action=signal.action,
            price=signal.price,
            confidence=signal.confidence,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            quantity=signal.quantity,
            reason=signal.reason,
            time=signal.time,
            risk_reward=round(risk_reward, 2),
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