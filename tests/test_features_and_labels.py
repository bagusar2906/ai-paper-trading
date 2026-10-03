from datetime import timezone

import numpy as np
import pandas as pd
import pytest

from app.features.core_v1 import (
    CORE_V1_FEATURE_COLUMNS,
    build_core_v1_features,
)
from app.features.dataset import build_training_dataset
from app.indicators import atr
from app.labels import FutureReturnLabel, add_future_return_label


def _candles(count=120):
    index = pd.date_range(
        "2026-01-01", periods=count, freq="5min", tz="UTC", name="Time"
    )
    base = 2000 + np.sin(np.arange(count) / 4) * 3 + np.arange(count) * 0.05
    open_ = base + np.sin(np.arange(count)) * 0.2
    close = base + np.cos(np.arange(count)) * 0.2
    return pd.DataFrame({
        "Open": open_,
        "High": np.maximum(open_, close) + 0.5,
        "Low": np.minimum(open_, close) - 0.5,
        "Close": close,
        "Volume": np.arange(count, dtype=float) + 100,
    }, index=index)


def test_atr_uses_only_current_and_prior_candles():
    df = _candles(20)
    values = atr(df, length=3)
    expected_second = max(
        df.iloc[1].High - df.iloc[1].Low,
        abs(df.iloc[1].High - df.iloc[0].Close),
        abs(df.iloc[1].Low - df.iloc[0].Close),
    )
    assert values.iloc[1] == pytest.approx((values.iloc[0] * 2 + expected_second) / 3)


def test_core_v1_feature_output_has_fixed_order_and_no_warmup_nulls():
    features = build_core_v1_features(_candles())
    assert tuple(features.columns) == CORE_V1_FEATURE_COLUMNS
    assert len(features) < 120
    assert not features.isna().any().any()


def test_feature_values_at_t_do_not_change_when_future_candles_change():
    baseline = _candles(120)
    changed = baseline.copy()
    changed.iloc[100:, changed.columns.get_loc("Open")] *= 1.2
    changed.iloc[100:, changed.columns.get_loc("Close")] *= 1.2
    changed.iloc[100:, changed.columns.get_loc("High")] *= 1.2
    changed.iloc[100:, changed.columns.get_loc("Low")] *= 1.2

    before = build_core_v1_features(baseline)
    after = build_core_v1_features(changed)
    pd.testing.assert_series_equal(before.loc[baseline.index[90]], after.loc[baseline.index[90]])


def test_future_return_label_is_aligned_to_its_exact_horizon():
    df = _candles(10)
    definition = FutureReturnLabel(horizon_candles=2, up_return_threshold=0.0001)
    labeled = add_future_return_label(df, definition)
    expected_return = df["Close"].iloc[2] / df["Close"].iloc[0] - 1
    assert labeled["future_return"].iloc[0] == pytest.approx(expected_return)
    assert labeled[definition.name].iloc[0] == int(expected_return >= 0.0001)
    assert pd.isna(labeled[definition.name].iloc[-1])
    assert pd.isna(labeled[definition.name].iloc[-2])


def test_training_dataset_snapshot_records_feature_and_label_versions():
    definition = FutureReturnLabel(horizon_candles=3, up_return_threshold=0.001)
    dataset = build_training_dataset(_candles(), definition)
    assert dataset.snapshot.feature_set_id == "core-v1"
    assert dataset.snapshot.label_definition_id == definition.definition_id
    assert dataset.snapshot.feature_columns == CORE_V1_FEATURE_COLUMNS
    assert dataset.snapshot.row_count == len(dataset.frame)
    assert dataset.frame.index.tz == timezone.utc


def test_feature_pipeline_rejects_naive_timestamps():
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        build_core_v1_features(_candles().tz_localize(None))
