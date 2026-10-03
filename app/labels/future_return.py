"""Future-return labels. These are for offline datasets only, never inference."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FutureReturnLabel:
    horizon_candles: int
    up_return_threshold: float
    name: str = "future_return_up"

    def __post_init__(self):
        if self.horizon_candles <= 0:
            raise ValueError("horizon_candles must be positive")
        if self.up_return_threshold <= 0:
            raise ValueError("up_return_threshold must be positive")

    @property
    def definition_id(self) -> str:
        threshold = format(self.up_return_threshold, ".12g")
        return f"{self.name}-n{self.horizon_candles}-t{threshold}"


def add_future_return_label(
    candles: pd.DataFrame,
    definition: FutureReturnLabel,
) -> pd.DataFrame:
    """Attach a label at t using close(t + N), leaving trailing labels null."""
    if "Close" not in candles:
        raise ValueError("candles are missing required column: Close")
    if not isinstance(candles.index, pd.DatetimeIndex):
        raise ValueError("candles must have a DatetimeIndex")
    if candles.index.tz is None:
        raise ValueError("candle timestamps must be timezone-aware UTC")

    result = candles.copy().sort_index()
    close = pd.to_numeric(result["Close"], errors="coerce")
    if close.isna().any() or (close <= 0).any():
        raise ValueError("Close must contain positive numeric values")
    future_return = close.shift(-definition.horizon_candles) / close - 1
    result["future_return"] = future_return
    result[definition.name] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    known = future_return.notna()
    result.loc[known, definition.name] = (
        future_return.loc[known] >= definition.up_return_threshold
    ).astype("int64")
    return result
