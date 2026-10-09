"""Crash-safe, chronological catch-up for the persistent paper-trading engine."""
from datetime import datetime, timezone
import json
import logging

import pandas as pd

from app.engine.result import EngineResult
from app.enums.trading_mode import TradingMode
from app.services.training_data_sync_service import COLUMNS, DURATIONS, TrainingDataSyncService

logger = logging.getLogger(__name__)


class TradingRecoveryService:
    PAGE_BARS = 1000

    def __init__(self, engine, now=None):
        self.engine = engine
        self.repos = engine.broker.repos
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.source = engine.provider.source_name
        self.symbol = engine.symbol.upper()
        self.timeframe = engine.timeframe
        self.duration = pd.Timedelta(DURATIONS[self.timeframe])

    def _checkpoint(self):
        return self.repos.trading_checkpoints.get(self.source, self.symbol, self.timeframe)

    @staticmethod
    def _time(checkpoint):
        return pd.Timestamp(checkpoint.candle_time, tz="UTC")

    @staticmethod
    def _decode(checkpoint):
        data = json.loads(checkpoint.history_json)
        frame = pd.DataFrame(data["data"], columns=COLUMNS,
                             index=pd.to_datetime(data["index"], utc=True))
        if frame.empty or frame.index[-1] != TradingRecoveryService._time(checkpoint):
            raise RuntimeError("Invalid paper trading checkpoint; resume point preserved")
        return frame

    @staticmethod
    def _encode(frame):
        return json.dumps({"index": [stamp.isoformat() for stamp in frame.index],
                           "data": frame[COLUMNS].to_numpy().tolist()}, allow_nan=False)

    def _normalize(self, frame, now):
        return TrainingDataSyncService._normalize(frame, self.duration, now)

    def _idle(self):
        positions = self.engine.broker.get_positions()
        return EngineResult(account=self.engine.get_account(),
                            position=positions[-1] if positions else None,
                            message="No new completed candles")

    def run(self):
        now = pd.Timestamp(self.now()).tz_convert("UTC")
        checkpoint = self._checkpoint()
        mode = self.engine.broker.get_trading_mode()
        if checkpoint is None or mode != TradingMode.AUTO:
            # First installation starts at the latest completed candle. Manual
            # operation establishes a fresh baseline without replaying entries.
            frame = self._normalize(self.engine._load_data(), now).tail(self.engine.bars)
            if frame.empty:
                raise RuntimeError("No completed candles available; resume point preserved")
            return self._process(frame) or self._idle()

        anchor = self._time(checkpoint)
        cursor = anchor
        processed = 0
        result = None
        # Release read transactions before provider requests or another writer.
        self.repos.session.rollback()
        while cursor + self.duration <= now:
            end = min(cursor + self.duration * self.PAGE_BARS, now)
            frame = self._normalize(self.engine.provider.get_history_range(
                self.symbol, self.timeframe, anchor, end), now)
            frame = frame[(frame.index >= anchor) & (frame.index < end)]
            if anchor not in frame.index:
                raise RuntimeError(
                    f"Backfill could not retrieve the last processed candle ({anchor.isoformat()}); "
                    "provider history may be unavailable. Resume point preserved.")
            for stamp in frame.index[frame.index > anchor]:
                next_result = self._process(frame.loc[[stamp]], replay=True)
                if next_result is not None:
                    if next_result.message == "Not enough data":
                        return next_result
                    result = next_result
                    processed += 1
            anchor = frame.index.max()
            cursor = end
        if result is None:
            return self._idle()
        result.message = f"Completed {processed} new candle(s); paper trading caught up"
        logger.info(result.message)
        return result

    def _process(self, incoming, replay=False):
        stamp = incoming.index[-1]
        broker = self.engine.broker
        previous_time = getattr(broker, "simulation_time", None)
        try:
            with self.repos.trading_transaction():
                # Re-read under the writer lock, including when another worker
                # has already advanced since this service fetched its data.
                checkpoint = self._checkpoint()
                if checkpoint is not None and self._time(checkpoint) >= stamp:
                    return None
                if replay and broker.get_trading_mode() != TradingMode.AUTO:
                    raise RuntimeError("Automatic catch-up paused because trading mode changed")
                history = incoming
                if replay and checkpoint is not None:
                    history = pd.concat([self._decode(checkpoint), incoming])
                    history = history[~history.index.duplicated(keep="last")].sort_index()
                history = history.tail(self.engine.bars)
                # Rehydrate balance before closing an old position. A previous
                # interrupted candle may have changed the broker's Python copy.
                broker._account = broker.get_account()
                broker.simulation_time = stamp.to_pydatetime()
                result = self.engine.run_once(df=history.copy())
                if result.message == "Not enough data":
                    return result
                diagnostic = getattr(result.signal, "execution_diagnostic", {})
                if diagnostic.get("reason") == "Decision journal failed":
                    raise RuntimeError("Decision journal failed; resume point preserved")
                self.repos.trading_checkpoints.save(
                    self.source, self.symbol, self.timeframe, stamp.to_pydatetime(), self._encode(history))
                return result
        finally:
            broker.simulation_time = previous_time
