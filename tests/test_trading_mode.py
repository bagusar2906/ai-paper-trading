from datetime import datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.engine.trading_engine import TradingEngine
from app.main import app
from app.strategy.ema_rsi_adx import EMARSIADXStrategy

client = TestClient(app)


class _FakeProvider:
    def __init__(self, n=150):
        self.n = n

    def get_history(self, symbol, timeframe, bars):
        idx = pd.date_range("2026-01-01", periods=self.n, freq="5min", name="Time")
        return pd.DataFrame(
            {
                "Open": [2000.0] * self.n,
                "High": [2001.0] * self.n,
                "Low": [1999.0] * self.n,
                "Close": [2000.0] * self.n,
                "Volume": [500.0] * self.n,
            },
            index=idx,
        )


def _forced_buy_strategy():
    strategy = EMARSIADXStrategy()

    def fake_prepare(df):
        f = df.copy()
        f["EMA"] = 1990.0
        f["ADX"] = 40.0
        f["RSI"] = 15.0
        f["+DI"] = 25.0
        f["-DI"] = 15.0
        f["is_green"] = True
        f["is_red"] = False
        f["rsi_exit_os"] = True
        f["rsi_exit_ob"] = False
        return f

    strategy.prepare = fake_prepare
    return strategy


# =============================================================================
# Settings API
# =============================================================================

def test_get_settings_defaults_to_manual():

    response = client.get("/settings")

    assert response.status_code == 200
    assert response.json()["trading_mode"] == "MANUAL"


def test_update_settings_to_auto():

    response = client.put("/settings", json={"trading_mode": "AUTO"})

    assert response.status_code == 200
    assert response.json()["trading_mode"] == "AUTO"

    response = client.get("/settings")
    assert response.json()["trading_mode"] == "AUTO"


def test_update_settings_rejects_invalid_mode():

    response = client.put("/settings", json={"trading_mode": "BOGUS"})

    assert response.status_code == 400


# =============================================================================
# Engine execution gating
# =============================================================================

def test_manual_mode_records_signal_but_does_not_execute(broker):

    strategy = _forced_buy_strategy()

    engine = TradingEngine(
        _FakeProvider(),
        strategy,
        broker,
        "XAUUSD",
        "5m",
        bars=150,
        respect_trading_mode=True,
    )

    result = engine.run_once()

    assert result.signal.action == "BUY"
    assert broker.get_positions() == []


def test_auto_mode_executes_with_risk_managed_quantity(broker):

    strategy = _forced_buy_strategy()

    engine = TradingEngine(
        _FakeProvider(),
        strategy,
        broker,
        "XAUUSD",
        "5m",
        bars=150,
        respect_trading_mode=True,
    )

    broker.repos.settings.set("trading_mode", "AUTO")

    engine.run_once()

    positions = broker.get_positions()

    assert len(positions) == 1
    # Regression: this used to silently fall back to a hardcoded 1.0
    # instead of the properly risk-sized quantity.
    assert positions[0].quantity != 1.0


def test_backtest_ignores_trading_mode_and_always_executes(broker):

    # A fresh broker always defaults to MANUAL - a backtest engine must
    # still execute regardless, or backtests would always show zero trades.
    strategy = _forced_buy_strategy()

    assert broker.get_trading_mode() == "MANUAL"

    engine = TradingEngine(
        _FakeProvider(),
        strategy,
        broker,
        "XAUUSD",
        "5m",
        bars=150,
        respect_trading_mode=False,
    )

    engine.run_once()

    assert len(broker.get_positions()) == 1
