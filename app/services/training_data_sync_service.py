"""Durable, page-by-page catch-up for self-training data."""
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.factories.repository_factory import RepositoryFactory
from app.market_data.contracts import CompletedCandle


DURATIONS = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
             "H1": "1h", "H4": "4h", "D1": "1d"}
COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


class TrainingDataSyncService:
    PAGE_BARS = 1000

    def __init__(self, repository_factory=RepositoryFactory, now=None):
        self.repository_factory = repository_factory
        self.now = now or (lambda: datetime.now(timezone.utc))

    def synchronize(self, provider, symbol, timeframe, bars):
        source = provider.source_name
        symbol = symbol.upper()
        duration = pd.Timedelta(DURATIONS[timeframe])
        now = pd.Timestamp(self.now()).tz_convert("UTC")
        repos = self.repository_factory()
        try:
            repository = repos.market_candles
            last = repository.latest_time(source, symbol, timeframe)
            resumed_from = pd.Timestamp(last).isoformat() if last else None
            inserted, pages = 0, 0
            if last is None:
                frame = self._normalize(provider.get_history(symbol, timeframe, min(bars + 1, 5000)), duration, now)
                if frame.empty:
                    raise RuntimeError("No completed candles available to initialize self-training history")
                inserted += self._save(repository, frame, source, symbol, timeframe)
                pages += 1
                last = frame.index.max()
            cursor = pd.Timestamp(last)
            # Re-fetch the last saved candle as an overlap. Source retention
            # problems must not silently skip the beginning of a downtime gap.
            anchor = cursor
            while cursor + duration <= now:
                end = min(cursor + duration * self.PAGE_BARS, now)
                # Keep a known candle in every request, including across
                # weekends/holidays. Some sources return errors for wholly
                # empty calendar intervals rather than an empty table.
                frame = self._normalize(provider.get_history_range(symbol, timeframe, anchor, end), duration, now)
                frame = frame[(frame.index >= anchor) & (frame.index < end)]
                if anchor not in frame.index:
                    raise RuntimeError(f"Backfill could not retrieve the last saved candle ({anchor.isoformat()}); provider history may be unavailable. Resume point preserved.")
                inserted += self._save(repository, frame, source, symbol, timeframe)
                anchor = frame.index.max()
                pages += 1
                cursor = end
            stored = repository.recent(source, symbol, timeframe, bars)
            candles = pd.DataFrame([
                {key: getattr(item, key.lower()) for key in COLUMNS} for item in stored
            ], index=pd.DatetimeIndex([item.candle_open_time for item in stored], tz="UTC", name="Time"))
            last_saved = repository.latest_time(source, symbol, timeframe)
            return candles, {"source": source, "symbol": symbol, "timeframe": timeframe,
                             "resumed_from": resumed_from, "last_candle_at": last_saved.isoformat() if last_saved else None,
                             "downloaded_bars": inserted, "pages": pages, "caught_up_through": now.isoformat(),
                             "training_window_bars": len(candles)}
        finally:
            repos.close()

    @staticmethod
    def _normalize(frame, duration, now):
        if not isinstance(frame, pd.DataFrame):
            raise RuntimeError("Provider did not return a candle table")
        if frame.empty:
            return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([], tz="UTC"))
        if not all(key in frame for key in COLUMNS):
            raise RuntimeError("Provider history is missing OHLCV columns")
        frame = frame[COLUMNS].copy()
        frame.index = pd.to_datetime(frame.index, utc=True)
        if frame.index.isna().any():
            raise RuntimeError("Provider history contains invalid timestamps")
        frame = frame[frame.index + duration <= now].sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        frame = frame.apply(pd.to_numeric, errors="coerce")
        if not np.isfinite(frame.to_numpy()).all() or (frame[["Open", "High", "Low", "Close"]] <= 0).any().any():
            raise RuntimeError("Provider history contains invalid prices or volume; resume point preserved")
        return frame

    @staticmethod
    def _save(repository, frame, source, symbol, timeframe):
        records = [CompletedCandle(source=source, symbol=symbol, timeframe=timeframe,
                                  candle_open_time=stamp.to_pydatetime(),
                                  **{key.lower(): float(row[key]) for key in COLUMNS})
                   for stamp, row in frame.iterrows()]
        return repository.upsert_batch(records)
