from types import SimpleNamespace

from app.models.strategy import Strategy
from app.services.dashboard_service import DashboardService


def test_dashboard_includes_active_strategy(monkeypatch):
    repos = SimpleNamespace(
        accounts=SimpleNamespace(get=lambda: object()),
        positions=SimpleNamespace(get_all=lambda: []),
        trades=SimpleNamespace(get_all=lambda: []),
        signals=SimpleNamespace(get_recent=lambda limit: []),
        strategies=SimpleNamespace(
            get_active=lambda: Strategy(
                id=2,
                name="Gold AI",
                strategy_type="AI_AGENT",
                config={"stop_loss_pips": 300, "risk_reward_ratio": 2},
                is_active=True,
            )
        ),
        close=lambda: None,
    )
    monkeypatch.setattr(
        "app.services.dashboard_service.RepositoryFactory",
        lambda: repos,
    )

    dashboard = DashboardService().get_dashboard()

    assert dashboard.active_strategy.name == "Gold AI"
    assert dashboard.active_strategy.strategy_type == "AI_AGENT"
    assert dashboard.active_strategy.stop_loss_pips == 300
    assert dashboard.active_strategy.take_profit_pips == 600
