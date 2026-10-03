"""Strict chronological walk-forward splits with an explicit label horizon gap."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WalkForwardConfig:
    initial_train_size: int
    validation_size: int
    step_size: int
    purge_candles: int
    embargo_candles: int = 0

    def __post_init__(self):
        if self.initial_train_size < 2 or self.validation_size < 1 or self.step_size < 1:
            raise ValueError("walk-forward sizes must be positive")
        if self.purge_candles < 0 or self.embargo_candles < 0:
            raise ValueError("purge and embargo must be non-negative")


@dataclass(frozen=True)
class WalkForwardFold:
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int


def generate_walk_forward_folds(row_count: int, config: WalkForwardConfig) -> list[WalkForwardFold]:
    """Create expanding train windows separated from validation by a purge gap.

    Index endpoints are exclusive. `purge_candles` should be at least the
    future-label horizon, so a training row's label can never inspect a price
    inside its validation window. `embargo_candles` creates an additional gap
    before the next validation anchor.
    """
    folds = []
    anchor = config.initial_train_size + config.purge_candles
    while anchor + config.validation_size <= row_count:
        folds.append(WalkForwardFold(
            train_start=0,
            train_end=anchor - config.purge_candles,
            validation_start=anchor,
            validation_end=anchor + config.validation_size,
        ))
        anchor += config.step_size + config.embargo_candles
    if not folds:
        raise ValueError("not enough rows for the configured walk-forward split")
    return folds
