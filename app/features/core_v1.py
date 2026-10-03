"""The shared, point-in-time-safe tabular feature set for the initial model."""

import math

import numpy as np
import pandas as pd

from app.indicators import adx_di, atr, ema, rsi, true_range


FEATURE_SET_ID = "core-v1"
FEATURE_SET_VERSION = 1

# This explicit order is a model contract. Training and inference must use it
# unchanged; a future feature change creates a new feature-set ID.
CORE_V1_FEATURE_COLUMNS = (
    "open", "high", "low", "close", "volume",
    "return_1", "return_3", "return_5", "return_10", "log_return_1",
    "ema_9", "ema_20", "ema_50", "ema_9_slope", "ema_20_slope",
    "close_to_ema_20", "ema_20_above_ema_50",
    "rsi_14", "rsi_14_change", "plus_di_14", "minus_di_14", "adx_14",
    "true_range", "atr_14", "atr_percent", "range_20",
    "body_percent", "upper_wick_percent", "lower_wick_percent",
    "close_location", "gap_percent", "candle_direction",
    "momentum_10", "consecutive_direction", "volatility_10", "volatility_20",
    "utc_hour_sin", "utc_hour_cos", "weekday_sin", "weekday_cos",
    "is_london_session", "is_new_york_session",
)

_REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


def _validate_ohlcv(candles: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(candles.index, pd.DatetimeIndex):
        raise ValueError("candles must have a DatetimeIndex")
    if candles.index.tz is None:
        raise ValueError("candle timestamps must be timezone-aware UTC")
    missing = [column for column in _REQUIRED_COLUMNS if column not in candles]
    if missing:
        raise ValueError(f"candles are missing required columns: {missing}")
    if candles.index.has_duplicates:
        raise ValueError("candle timestamps must be unique")

    df = candles.loc[:, _REQUIRED_COLUMNS].copy().sort_index()
    for column in _REQUIRED_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    if df.isna().any().any():
        raise ValueError("candles contain non-numeric OHLCV values")
    if (df["Volume"] < 0).any():
        raise ValueError("candle volume cannot be negative")
    if (df["High"] < df[["Open", "Close"]].max(axis=1)).any():
        raise ValueError("candle high cannot be below open or close")
    if (df["Low"] > df[["Open", "Close"]].min(axis=1)).any():
        raise ValueError("candle low cannot be above open or close")
    return df


def _consecutive_direction(direction: pd.Series) -> pd.Series:
    """Positive/negative run length, calculated solely from previous candles."""
    result = []
    previous = 0.0
    run = 0
    for value in direction:
        if value == 0:
            run = 0
        elif value == previous:
            run += int(value)
        else:
            run = int(value)
        result.append(run)
        previous = value
    return pd.Series(result, index=direction.index, dtype=float)


def build_core_v1_features(
    candles: pd.DataFrame,
    *,
    drop_warmup: bool = True,
) -> pd.DataFrame:
    """Build `core-v1` features known at each completed candle close.

    No future row is read. Rows without enough lookback history are either
    retained with explicit missing values or removed through `drop_warmup`.
    """
    df = _validate_ohlcv(candles)
    features = pd.DataFrame(index=df.index)
    features["open"] = df["Open"]
    features["high"] = df["High"]
    features["low"] = df["Low"]
    features["close"] = df["Close"]
    features["volume"] = df["Volume"]

    for periods in (1, 3, 5, 10):
        features[f"return_{periods}"] = df["Close"].pct_change(periods=periods)
    features["log_return_1"] = np.log(df["Close"] / df["Close"].shift(1))

    for length in (9, 20, 50):
        features[f"ema_{length}"] = ema(df["Close"], length)
    features["ema_9_slope"] = features["ema_9"].pct_change()
    features["ema_20_slope"] = features["ema_20"].pct_change()
    features["close_to_ema_20"] = df["Close"] / features["ema_20"] - 1
    features["ema_20_above_ema_50"] = (
        features["ema_20"] > features["ema_50"]
    ).astype(float)

    features["rsi_14"] = rsi(df["Close"], 14)
    features["rsi_14_change"] = features["rsi_14"].diff()
    plus_di, minus_di, adx = adx_di(df, 14, 14)
    features["plus_di_14"] = plus_di
    features["minus_di_14"] = minus_di
    features["adx_14"] = adx

    features["true_range"] = true_range(df)
    features["atr_14"] = atr(df, 14)
    features["atr_percent"] = features["atr_14"] / df["Close"]
    features["range_20"] = (
        df["High"].rolling(20).max() / df["Low"].rolling(20).min() - 1
    )

    candle_range = (df["High"] - df["Low"]).replace(0, np.nan)
    body = df["Close"] - df["Open"]
    features["body_percent"] = body / candle_range
    features["upper_wick_percent"] = (
        df["High"] - df[["Open", "Close"]].max(axis=1)
    ) / candle_range
    features["lower_wick_percent"] = (
        df[["Open", "Close"]].min(axis=1) - df["Low"]
    ) / candle_range
    features["close_location"] = (df["Close"] - df["Low"]) / candle_range
    features["gap_percent"] = df["Open"] / df["Close"].shift(1) - 1
    direction = np.sign(body)
    features["candle_direction"] = direction

    features["momentum_10"] = df["Close"].pct_change(10)
    features["consecutive_direction"] = _consecutive_direction(direction)
    features["volatility_10"] = features["log_return_1"].rolling(10).std()
    features["volatility_20"] = features["log_return_1"].rolling(20).std()

    utc_index = df.index.tz_convert("UTC")
    features["utc_hour_sin"] = np.sin(2 * math.pi * utc_index.hour / 24)
    features["utc_hour_cos"] = np.cos(2 * math.pi * utc_index.hour / 24)
    features["weekday_sin"] = np.sin(2 * math.pi * utc_index.dayofweek / 7)
    features["weekday_cos"] = np.cos(2 * math.pi * utc_index.dayofweek / 7)
    features["is_london_session"] = ((utc_index.hour >= 7) & (utc_index.hour < 16)).astype(float)
    features["is_new_york_session"] = ((utc_index.hour >= 13) & (utc_index.hour < 22)).astype(float)

    features = features.loc[:, CORE_V1_FEATURE_COLUMNS]
    return features.dropna() if drop_warmup else features
