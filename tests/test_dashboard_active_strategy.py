from datetime import datetime, timedelta
from types import SimpleNamespace

from app.models.strategy import Strategy
from app.models.signal import TradingSignal
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


def test_dashboard_shows_latest_fifteen_signals_first(monkeypatch):
    oldest = datetime(2026, 10, 4, 9, 0)
    signals = [
        TradingSignal(
            symbol="XAUUSD",
            action="HOLD",
            price=2000.0,
            time=oldest + timedelta(minutes=5 * index),
            confidence=0.5,
            reason="test",
        )
        for index in range(15)
    ]
    recent_limits = []

    repos = SimpleNamespace(
        accounts=SimpleNamespace(get=lambda: object()),
        positions=SimpleNamespace(get_all=lambda: []),
        trades=SimpleNamespace(get_all=lambda: []),
        signals=SimpleNamespace(
            get_recent=lambda limit: recent_limits.append(limit) or signals
        ),
        strategies=SimpleNamespace(get_active=lambda: None),
        close=lambda: None,
    )
    monkeypatch.setattr(
        "app.services.dashboard_service.RepositoryFactory",
        lambda: repos,
    )

    dashboard = DashboardService().get_dashboard()

    assert recent_limits == [15]
    assert dashboard.signals == list(reversed(signals))
    assert dashboard.current_signal.time == signals[-1].time
