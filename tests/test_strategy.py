import numpy as np
import pandas as pd
import pytest

from app.strategy.ema_rsi_adx import EMARSIADXStrategy
from app.models.signal import TradingSignal


def _base_df(n=5):
    idx = pd.date_range("2026-01-01", periods=n, freq="5min")
    return pd.DataFrame(
        {
            "Open": [2000.0] * n,
            "High": [2001.0] * n,
            "Low": [1999.0] * n,
            "Close": [2000.0] * n,
            "Volume": [500.0] * n,
        },
        index=idx,
    )


def _with_forced_indicators(df, ema, rsi, adx, plus_di, minus_di):
    """Bypass real indicator math so we can deterministically hit each branch
    of the strategy's decision logic."""
    df = df.copy()
    df["EMA"] = ema
    df["RSI"] = rsi
    df["ADX"] = adx
    df["+DI"] = plus_di
    df["-DI"] = minus_di
    return df


def test_trading_signal_is_instantiable():
    # Regression test: TradingSignal used to inherit from the abstract
    # Strategy base class, which made it impossible to construct.
    signal = TradingSignal(
        symbol="XAUUSD", action="HOLD", price=2000.0, time="2026-01-01",
        ema=2000.0, rsi=50.0, adx=20.0, plus_di=20.0, minus_di=20.0,
    )
    assert signal.action == "HOLD"


def test_buy_signal_triggers_on_oversold_uptrend(monkeypatch):
    strategy = EMARSIADXStrategy()
    df = _base_df()
    prepared = _with_forced_indicators(
        df, ema=1990.0, rsi=10.0, adx=40.0, plus_di=30.0, minus_di=10.0
    )
    monkeypatch.setattr(strategy, "prepare", lambda df: prepared)

    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action == "BUY"
    assert isinstance(signal, TradingSignal)


def test_sell_signal_triggers_on_overbought_downtrend(monkeypatch):
    strategy = EMARSIADXStrategy()
    df = _base_df()
    prepared = _with_forced_indicators(
        df, ema=2010.0, rsi=90.0, adx=40.0, plus_di=10.0, minus_di=30.0
    )
    monkeypatch.setattr(strategy, "prepare", lambda df: prepared)

    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action == "SELL"


def test_hold_signal_when_no_setup(monkeypatch):
    strategy = EMARSIADXStrategy()
    df = _base_df()
    prepared = _with_forced_indicators(
        df, ema=2000.0, rsi=50.0, adx=10.0, plus_di=20.0, minus_di=20.0
    )
    monkeypatch.setattr(strategy, "prepare", lambda df: prepared)

    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action == "HOLD"
    assert signal.reason == "No setup"


def test_generate_signal_with_real_indicators_does_not_crash():
    """End-to-end sanity check using the strategy's real prepare()."""
    rng = np.random.default_rng(0)
    n = 60
    close = 2000 + np.cumsum(rng.normal(0, 1, n))
    idx = pd.date_range("2026-01-01", periods=n, freq="5min")
    df = pd.DataFrame(
        {
            "Open": close,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": rng.uniform(100, 1000, n),
        },
        index=idx,
    )

    strategy = EMARSIADXStrategy()
    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action in {"BUY", "SELL", "HOLD"}
