from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():

    response = client.get("/health")

    assert response.status_code == 200

    assert response.json()["status"] == "ok"


def test_signal():

    response = client.get("/signal")

    assert response.status_code == 200

    data = response.json()

    assert "symbol" in data
    assert "action" in data


# =============================================================================
# Orders / Quote
#
# Regression tests for: the /orders router never being registered on the
# app, the endpoint being declared as GET instead of POST, and /quote not
# existing at all (which left the order form's price field empty and
# silently blocked every submission client-side).
# =============================================================================

def _fake_provider(price=2000.0):

    class FakeProvider:
        def get_current_price(self, symbol):
            return price

        def disconnect(self):
            pass

        def connect(self):
            return True

    return FakeProvider()


def test_quote_endpoint_returns_bid_ask(monkeypatch):

    monkeypatch.setattr(
        "app.api.quote.create_provider",
        lambda name=None: _fake_provider(2000.0),
    )

    response = client.get("/quote?symbol=XAUUSD")

    assert response.status_code == 200

    data = response.json()

    assert data["symbol"] == "XAUUSD"
    assert data["bid"] < 2000.0 < data["ask"]


def test_place_order_endpoint_accepts_post():

    order = {
        "symbol": "XAUUSD",
        "action": "BUY",
        "price": 2000.0,
        "quantity": 1.0,
        "stop_loss": 1995.0,
        "take_profit": 2010.0,
    }

    response = client.post("/orders", json=order)

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True


def test_place_order_endpoint_rejects_get():

    # The endpoint used to be declared with @router.get, which the
    # frontend's POST request would never have matched.
    response = client.get("/orders")

    assert response.status_code == 405


def test_place_order_then_appears_on_dashboard():

    order = {
        "symbol": "XAUUSD",
        "action": "BUY",
        "price": 2000.0,
        "quantity": 1.0,
        "stop_loss": 1995.0,
        "take_profit": 2010.0,
    }

    client.post("/orders", json=order)

    response = client.get("/dashboard")

    assert response.status_code == 200

    data = response.json()

    assert len(data["positions"]) == 1
    assert data["positions"][0]["symbol"] == "XAUUSD"


def test_chart_endpoint_includes_open_positions(monkeypatch):

    # Regression test: ChartPosition was missing a `quantity` field that
    # chart_service.py passed anyway, so /chart raised a TypeError as soon
    # as any position was open.

    import pandas as pd

    N = 150

    class FakeProvider:
        def get_history(self, symbol, timeframe, bars):
            idx = pd.date_range(
                "2026-01-01", periods=N, freq="5min", name="Time"
            )
            return pd.DataFrame(
                {
                    "Open": [2000.0] * N,
                    "High": [2001.0] * N,
                    "Low": [1999.0] * N,
                    "Close": [2000.0] * N,
                    "Volume": [500.0] * N,
                },
                index=idx,
            )

        def disconnect(self):
            pass

        def connect(self):
            return True

    monkeypatch.setattr(
        "app.services.chart_service.create_provider",
        lambda name=None: FakeProvider(),
    )

    order = {
        "symbol": "XAUUSD",
        "action": "BUY",
        "price": 2000.0,
        "quantity": 1.0,
        "stop_loss": 1995.0,
        "take_profit": 2010.0,
    }

    client.post("/orders", json=order)

    response = client.get("/chart")

    assert response.status_code == 200

    data = response.json()

    assert len(data["positions"]) == 1
    assert data["positions"][0]["symbol"] == "XAUUSD"
    assert data["positions"][0]["quantity"] == 1.0