"""Volatility indicators."""

import pandas as pd


def true_range(df: pd.DataFrame) -> pd.Series:
    """Point-in-time true range for canonical OHLC candles."""
    high = df["High"]
    low = df["Low"]
    previous_close = df["Close"].shift(1)
    return pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Wilder-style average true range using only present/past candles."""
    if length <= 0:
        raise ValueError("ATR length must be positive")
    return true_range(df).ewm(alpha=1 / length, adjust=False).mean()
