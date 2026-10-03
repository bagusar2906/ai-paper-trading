from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.strategy import Strategy
from app.strategy import strategy_router


def test_activate_strategy_marks_it_active(monkeypatch):
    repos = MagicMock()
    service = MagicMock()
    active = Strategy(id=7, name="AI", strategy_type="AI_AGENT", is_active=True)
    service.set_active.return_value = active

    monkeypatch.setattr(
        strategy_router,
        "create_service",
        lambda: (repos, service),
    )
    app = FastAPI()
    app.include_router(strategy_router.router)

    response = TestClient(app).post("/strategy/7/activate")

    assert response.status_code == 200
    assert response.json()["is_active"] is True
    service.set_active.assert_called_once_with(7)
    repos.close.assert_called_once()


def test_activate_missing_strategy_returns_404(monkeypatch):
    repos = MagicMock()
    service = MagicMock()
    service.set_active.return_value = None
    monkeypatch.setattr(
        strategy_router,
        "create_service",
        lambda: (repos, service),
    )
    app = FastAPI()
    app.include_router(strategy_router.router)

    response = TestClient(app).post("/strategy/99/activate")

    assert response.status_code == 404
