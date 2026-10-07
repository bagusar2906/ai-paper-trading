"""Indicator-free market history: twelve completed OHLCV candles."""

import pandas as pd

from app.features.core_v1 import _validate_ohlcv

FEATURE_SET_ID = "raw-ohlcv-v1"
FEATURE_SET_VERSION = 1
LOOKBACK_CANDLES = 12
RAW_OHLCV_FEATURE_COLUMNS = tuple(
    f"{field.lower()}_lag_{lag}"
    for lag in range(LOOKBACK_CANDLES)
    for field in ("Open", "High", "Low", "Close", "Volume")
)


def build_raw_ohlcv_features(candles, *, drop_warmup=True):
    """Use only current and previous raw prices/volume, without indicators."""
    frame = _validate_ohlcv(candles)
    features = pd.DataFrame({
        f"{field.lower()}_lag_{lag}": frame[field].shift(lag)
        for lag in range(LOOKBACK_CANDLES)
        for field in ("Open", "High", "Low", "Close", "Volume")
    }, index=frame.index)
    return features.dropna() if drop_warmup else features
