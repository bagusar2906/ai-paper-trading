import numpy as np
import pandas as pd
import pytest

from app.indicators import ema, rsi, adx_di, obv, cmf, relative_volume


def _make_ohlcv(n=100, seed=42):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0, 1, n)
    low = close - rng.uniform(0, 1, n)
    open_ = close + rng.normal(0, 0.5, n)
    volume = rng.uniform(100, 1000, n)

    idx = pd.date_range("2026-01-01", periods=n, freq="5min")
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


def test_ema_length_matches_input():
    df = _make_ohlcv()
    result = ema(df["Close"], 20)
    assert len(result) == len(df)
    assert not result.isna().any()


def test_rsi_bounded_between_0_and_100():
    df = _make_ohlcv()
    result = rsi(df["Close"], 14)
    valid = result.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_adx_di_returns_three_series_same_length():
    df = _make_ohlcv()
    plus_di, minus_di, adx = adx_di(df, 14, 14)
    assert len(plus_di) == len(df)
    assert len(minus_di) == len(df)
    assert len(adx) == len(df)


def test_obv_is_cumulative_and_signed():
    df = _make_ohlcv()
    result = obv(df["Close"], df["Volume"])
    assert len(result) == len(df)
    # First value should be 0 since diff() of the first bar is NaN -> filled to 0
    assert result.iloc[0] == 0


def test_cmf_bounded_between_negative_1_and_1():
    df = _make_ohlcv()
    result = cmf(df, length=20)
    valid = result.dropna()
    assert (valid >= -1.0001).all() and (valid <= 1.0001).all()


def test_relative_volume_is_positive():
    df = _make_ohlcv()
    result = relative_volume(df["Volume"], length=20)
    valid = result.dropna()
    assert (valid > 0).all()
