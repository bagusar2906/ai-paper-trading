import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_signal_endpoint(monkeypatch, tmp_path):
    # Point the DB at a scratch file so this test doesn't touch real data.
    # Must be patched *before* the startup event runs (i.e. before entering
    # the TestClient context), since that's what creates the table.
    monkeypatch.setattr("app.database.database.DB_PATH", tmp_path / "test.db")

    rng = np.random.default_rng(2)
    n = 60
    close = 2000 + np.cumsum(rng.normal(0, 1, n))
    idx = pd.date_range("2026-01-01", periods=n, freq="5min")
    fake_df = pd.DataFrame(
        {
            "Open": close,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": rng.uniform(100, 1000, n),
        },
        index=idx,
    )

    class FakeProvider:
        def get_history(self, symbol, timeframe, bars):
            return fake_df

        def disconnect(self):
            pass

    monkeypatch.setattr("app.main.create_provider", lambda: FakeProvider())

    with TestClient(app) as client:
        resp = client.get("/signal")
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] in {"BUY", "SELL", "HOLD"}
    assert body["symbol"] == "XAUUSD"


def test_history_endpoint(monkeypatch, tmp_path):
    monkeypatch.setattr("app.database.database.DB_PATH", tmp_path / "test.db")

    with TestClient(app) as client:
        resp = client.get("/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
