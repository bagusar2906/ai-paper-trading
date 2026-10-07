"""Offline dataset assembly with explicit, reproducible metadata."""

from dataclasses import dataclass

import pandas as pd

from app.features.core_v1 import (
    CORE_V1_FEATURE_COLUMNS,
    FEATURE_SET_ID,
    FEATURE_SET_VERSION,
    build_core_v1_features,
)
from app.labels.future_return import FutureReturnLabel, add_future_return_label
from app.features.raw_ohlcv_v1 import (
    FEATURE_SET_ID as RAW_FEATURE_SET_ID,
    FEATURE_SET_VERSION as RAW_FEATURE_SET_VERSION,
    RAW_OHLCV_FEATURE_COLUMNS, build_raw_ohlcv_features,
)


@dataclass(frozen=True)
class DatasetSnapshot:
    feature_set_id: str
    feature_set_version: int
    label_definition_id: str
    feature_columns: tuple[str, ...]
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    row_count: int


@dataclass(frozen=True)
class TrainingDataset:
    frame: pd.DataFrame
    snapshot: DatasetSnapshot


def build_training_dataset(
    candles: pd.DataFrame,
    label_definition: FutureReturnLabel,
    feature_set_id: str = FEATURE_SET_ID,
) -> TrainingDataset:
    """Join same-timestamp point-in-time features to offline future labels."""
    if feature_set_id == FEATURE_SET_ID:
        features = build_core_v1_features(candles, drop_warmup=True)
        version, columns = FEATURE_SET_VERSION, CORE_V1_FEATURE_COLUMNS
    elif feature_set_id == RAW_FEATURE_SET_ID:
        features = build_raw_ohlcv_features(candles, drop_warmup=True)
        version, columns = RAW_FEATURE_SET_VERSION, RAW_OHLCV_FEATURE_COLUMNS
    else:
        raise ValueError(f"unsupported feature set: {feature_set_id}")
    labels = add_future_return_label(candles, label_definition)
    label_series = labels[label_definition.name]
    frame = features.join(label_series, how="inner").dropna(
        subset=[label_definition.name]
    )
    if frame.empty:
        raise ValueError("no rows remain after feature warm-up and label horizon")
    snapshot = DatasetSnapshot(
        feature_set_id=feature_set_id,
        feature_set_version=version,
        label_definition_id=label_definition.definition_id,
        feature_columns=columns,
        start_time=frame.index.min(),
        end_time=frame.index.max(),
        row_count=len(frame),
    )
    return TrainingDataset(frame=frame, snapshot=snapshot)
