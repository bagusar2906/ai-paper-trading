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
) -> TrainingDataset:
    """Join same-timestamp point-in-time features to offline future labels."""
    features = build_core_v1_features(candles, drop_warmup=True)
    labels = add_future_return_label(candles, label_definition)
    label_series = labels[label_definition.name]
    frame = features.join(label_series, how="inner").dropna(
        subset=[label_definition.name]
    )
    if frame.empty:
        raise ValueError("no rows remain after feature warm-up and label horizon")
    snapshot = DatasetSnapshot(
        feature_set_id=FEATURE_SET_ID,
        feature_set_version=FEATURE_SET_VERSION,
        label_definition_id=label_definition.definition_id,
        feature_columns=CORE_V1_FEATURE_COLUMNS,
        start_time=frame.index.min(),
        end_time=frame.index.max(),
        row_count=len(frame),
    )
    return TrainingDataset(frame=frame, snapshot=snapshot)
