from app.models.dashboard.dashboard_response import DashboardResponse
from app.models.dashboard.dashboard_statistics import DashboardStatistics
from app.models.dashboard.signal_response import SignalResponse
from app.models.dashboard.active_strategy_response import ActiveStrategyResponse
from app.factories.repository_factory import RepositoryFactory


class DashboardService:

    def __init__(self):

        pass

    def get_dashboard(self):

        repos = RepositoryFactory()

        try:

            account = repos.accounts.get()
            print(f"Account: {account}")

            positions = repos.positions.get_all()

            trades = repos.trades.get_all()

            # The repository returns history in chronological order for chart
            # consumers. The dashboard table is a history view, so show the
            # most recent 15 signals first without changing that shared order.
            signals = list(reversed(repos.signals.get_recent(15)))

            active_strategy = self._build_active_strategy(
                repos.strategies.get_active()
            )

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
                active_strategy=active_strategy,
            )

        finally:

            # DashboardService is a module-level singleton (see api/dashboard.py),
            # so opening the session in __init__ would either leak permanently
            # (never closed) or, if closed too early, break every call after the
            # first. Scoping it here instead keeps each /dashboard request isolated.
            repos.close()

    @staticmethod
    def _build_active_strategy(strategy) -> ActiveStrategyResponse | None:

        if strategy is None:
            return None

        config = strategy.config or {}
        stop_loss_pips = config.get("stop_loss_pips")
        risk_reward_ratio = config.get(
            "risk_reward_ratio",
            config.get("risk_reward"),
        )

        try:
            stop_loss_pips = float(stop_loss_pips)
        except (TypeError, ValueError):
            stop_loss_pips = None

        try:
            risk_reward_ratio = float(risk_reward_ratio)
        except (TypeError, ValueError):
            risk_reward_ratio = None

        take_profit_pips = (
            stop_loss_pips * risk_reward_ratio
            if stop_loss_pips is not None and risk_reward_ratio is not None
            else None
        )

        return ActiveStrategyResponse(
            id=strategy.id,
            name=strategy.name,
            strategy_type=strategy.strategy_type,
            stop_loss_pips=stop_loss_pips,
            take_profit_pips=take_profit_pips,
            risk_reward_ratio=risk_reward_ratio,
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
