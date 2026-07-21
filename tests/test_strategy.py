import numpy as np
import pandas as pd
import pytest

from app.strategy.ema_rsi_adx import EMARSIADXStrategy
from app.models.signal import TradingSignal
from app.config import StrategyConfig


def _base_df(n=5, opens=None, closes=None):
    """Build an n-row OHLCV frame. By default every bar is flat (Open==Close)
    so tests must opt in to candle color via `opens`/`closes`."""
    idx = pd.date_range("2026-01-01", periods=n, freq="5min")
    opens = opens if opens is not None else [2000.0] * n
    closes = closes if closes is not None else [2000.0] * n
    return pd.DataFrame(
        {
            "Open": opens,
            "High": [max(o, c) + 1.0 for o, c in zip(opens, closes)],
            "Low": [min(o, c) - 1.0 for o, c in zip(opens, closes)],
            "Close": closes,
            "Volume": [500.0] * n,
        },
        index=idx,
    )


def _with_forced_indicators(df, ema, rsi, adx, plus_di=20.0, minus_di=20.0):
    """Bypass real indicator math so we can deterministically hit each branch
    of the strategy's decision logic.

    `rsi` may be a single value (applied to every row, i.e. no RSI crossing
    ever occurs) or a list matching len(df) so callers can control the
    previous-bar vs. current-bar RSI values needed for the crossback check.
    """
    df = df.copy()
    df["EMA"] = ema
    df["RSI"] = rsi
    df["ADX"] = adx
    df["+DI"] = plus_di
    df["-DI"] = minus_di
    return df


def _two_bar_scenario(
    prev_rsi,
    last_rsi,
    prev_close=2000.0,
    last_open=2000.0,
    last_close=2000.0,
    ema=2000.0,
    adx=40.0,
):
    """Two-bar frame: bar 0 only supplies the previous RSI value (needed for
    the crossback check), bar 1 is the "current" bar the strategy decides
    on, with its own Open/Close (candle color) and EMA/ADX."""
    df = _base_df(
        n=2,
        opens=[prev_close, last_open],
        closes=[prev_close, last_close],
    )
    return _with_forced_indicators(
        df,
        ema=[ema, ema],
        rsi=[prev_rsi, last_rsi],
        adx=[adx, adx],
    )


def test_trading_signal_is_instantiable():
    # Regression test: TradingSignal used to inherit from the abstract
    # Strategy base class, which made it impossible to construct.
    signal = TradingSignal(
        symbol="XAUUSD", action="HOLD", price=2000.0, time="2026-01-01",
        ema=2000.0, rsi=50.0, adx=20.0, plus_di=20.0, minus_di=20.0,
    )
    assert signal.action == "HOLD"


# =============================================================================
# BUY
# =============================================================================

def test_buy_signal_triggers_on_rsi_crossback_with_green_candle(monkeypatch):
    """Mirrors the Pine Script 1:1: uptrend + strong ADX + green candle +
    RSI crossing back above the oversold line this bar."""
    strategy = EMARSIADXStrategy()
    df = _base_df(n=2)
    prepared = _two_bar_scenario(
        prev_rsi=15.0,          # below RSI_OS (20) last bar
        last_rsi=25.0,          # back above RSI_OS this bar -> crossing
        last_open=2000.0,
        last_close=2005.0,      # green candle (close > open)
        ema=1990.0,             # close > EMA -> uptrend
        adx=40.0,               # > ADX_LEVEL (30)
    )
    monkeypatch.setattr(strategy, "prepare", lambda df: prepared)

    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action == "BUY"
    assert isinstance(signal, TradingSignal)
    assert signal.stop_loss is not None
    assert signal.take_profit is not None
    assert signal.take_profit > signal.price > signal.stop_loss


def test_no_buy_without_candle_color_confirmation(monkeypatch):
    """Same trend/ADX/RSI-crossback setup as a valid BUY, but the current
    bar closed red instead of green -> must NOT trigger."""
    strategy = EMARSIADXStrategy()
    df = _base_df(n=2)
    prepared = _two_bar_scenario(
        prev_rsi=15.0,
        last_rsi=25.0,
        last_open=2005.0,
        last_close=2000.0,      # red candle (close < open)
        ema=1990.0,
        adx=40.0,
    )
    monkeypatch.setattr(strategy, "prepare", lambda df: prepared)

    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action == "HOLD"


def test_no_buy_when_rsi_is_below_threshold_but_not_crossing(monkeypatch):
    """Regression guard: the old implementation fired on a *static*
    RSI < RSI_OS check. The real indicator only fires on the crossing
    event, so two consecutive oversold bars (no cross) must stay HOLD."""
    strategy = EMARSIADXStrategy()
    df = _base_df(n=2)
    prepared = _two_bar_scenario(
        prev_rsi=10.0,           # already oversold last bar...
        last_rsi=15.0,           # ...and still oversold this bar (no cross)
        last_open=2000.0,
        last_close=2005.0,
        ema=1990.0,
        adx=40.0,
    )
    monkeypatch.setattr(strategy, "prepare", lambda df: prepared)

    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action == "HOLD"


# =============================================================================
# SELL
# =============================================================================

def test_sell_signal_triggers_on_rsi_crossback_with_red_candle(monkeypatch):
    strategy = EMARSIADXStrategy()
    df = _base_df(n=2)
    prepared = _two_bar_scenario(
        prev_rsi=85.0,           # above RSI_OB (80) last bar
        last_rsi=75.0,           # back below RSI_OB this bar -> crossing
        last_open=2005.0,
        last_close=2000.0,       # red candle
        ema=2010.0,              # close < EMA -> downtrend
        adx=40.0,
    )
    monkeypatch.setattr(strategy, "prepare", lambda df: prepared)

    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action == "SELL"
    assert signal.stop_loss is not None
    assert signal.take_profit is not None
    assert signal.take_profit < signal.price < signal.stop_loss


def test_no_sell_without_candle_color_confirmation(monkeypatch):
    strategy = EMARSIADXStrategy()
    df = _base_df(n=2)
    prepared = _two_bar_scenario(
        prev_rsi=85.0,
        last_rsi=75.0,
        last_open=2000.0,
        last_close=2005.0,       # green candle -> should block SELL
        ema=2010.0,
        adx=40.0,
    )
    monkeypatch.setattr(strategy, "prepare", lambda df: prepared)

    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action == "HOLD"


def test_no_sell_when_rsi_is_above_threshold_but_not_crossing(monkeypatch):
    strategy = EMARSIADXStrategy()
    df = _base_df(n=2)
    prepared = _two_bar_scenario(
        prev_rsi=90.0,
        last_rsi=85.0,            # still overbought, no cross back below 80
        last_open=2005.0,
        last_close=2000.0,
        ema=2010.0,
        adx=40.0,
    )
    monkeypatch.setattr(strategy, "prepare", lambda df: prepared)

    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action == "HOLD"


# =============================================================================
# HOLD / edge cases
# =============================================================================

def test_hold_signal_when_adx_below_level(monkeypatch):
    strategy = EMARSIADXStrategy()
    df = _base_df(n=2)
    prepared = _two_bar_scenario(
        prev_rsi=15.0,
        last_rsi=25.0,
        last_open=2000.0,
        last_close=2005.0,
        ema=1990.0,
        adx=10.0,                # below ADX_LEVEL -> no trend strength
    )
    monkeypatch.setattr(strategy, "prepare", lambda df: prepared)

    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action == "HOLD"
    assert signal.reason == "No setup"


def test_hold_signal_with_only_one_bar_of_history(monkeypatch):
    """Can't detect an RSI crossback with fewer than 2 bars -> must not
    raise and must fall back to HOLD."""
    strategy = EMARSIADXStrategy()
    df = _base_df(n=1)
    prepared = _with_forced_indicators(
        df, ema=1990.0, rsi=25.0, adx=40.0,
    )
    monkeypatch.setattr(strategy, "prepare", lambda df: prepared)

    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action == "HOLD"


def test_generate_signal_with_real_indicators_does_not_crash():
    """End-to-end sanity check using the strategy's real prepare()."""
    rng = np.random.default_rng(0)
    n = 60
    close = 2000 + np.cumsum(rng.normal(0, 1, n))
    open_ = close + rng.normal(0, 0.5, n)
    idx = pd.date_range("2026-01-01", periods=n, freq="5min")
    df = pd.DataFrame(
        {
            "Open": open_,
            "High": np.maximum(open_, close) + 0.5,
            "Low": np.minimum(open_, close) - 0.5,
            "Close": close,
            "Volume": rng.uniform(100, 1000, n),
        },
        index=idx,
    )

    strategy = EMARSIADXStrategy()
    signal = strategy.generate_signal("XAUUSD", df)

    assert signal.action in {"BUY", "SELL", "HOLD"}


def test_generate_signal_over_many_windows_never_crashes():
    """Replays a longer synthetic series bar-by-bar (like the backtest
    engine does) to make sure no window size / edge case blows up the
    crossback logic."""
    rng = np.random.default_rng(7)
    n = 150
    close = 2000 + np.cumsum(rng.normal(0, 1, n))
    open_ = close + rng.normal(0, 0.5, n)
    idx = pd.date_range("2026-01-01", periods=n, freq="5min")
    df = pd.DataFrame(
        {
            "Open": open_,
            "High": np.maximum(open_, close) + 0.5,
            "Low": np.minimum(open_, close) - 0.5,
            "Close": close,
            "Volume": rng.uniform(100, 1000, n),
        },
        index=idx,
    )

    strategy = EMARSIADXStrategy()

    for i in range(2, n):
        signal = strategy.generate_signal("XAUUSD", df.iloc[: i + 1])
        assert signal.action in {"BUY", "SELL", "HOLD"}
