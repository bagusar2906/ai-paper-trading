from datetime import timezone

from app.database.models import MarketCandleEntity
from app.market_data.contracts import CompletedCandle
from app.repositories.base_repository import BaseRepository


class MarketCandleRepository(BaseRepository):
    """Idempotent storage for completed candles from any supported source."""

    def upsert(self, candle: CompletedCandle) -> MarketCandleEntity:
        # SQLite does not retain timezone metadata. Store normalized UTC values
        # as naive timestamps consistently; the boundary contract remains UTC.
        candle_time = candle.candle_open_time.astimezone(timezone.utc).replace(
            tzinfo=None
        )
        ingested_at = candle.ingested_at.astimezone(timezone.utc).replace(
            tzinfo=None
        )
        entity = (
            self.session.query(MarketCandleEntity)
            .filter_by(
                source=candle.source,
                symbol=candle.symbol,
                timeframe=candle.timeframe,
                candle_open_time=candle_time,
            )
            .one_or_none()
        )
        if entity is None:
            entity = MarketCandleEntity(
                source=candle.source,
                symbol=candle.symbol,
                timeframe=candle.timeframe,
                candle_open_time=candle_time,
            )
            self.session.add(entity)

        entity.open = candle.open
        entity.high = candle.high
        entity.low = candle.low
        entity.close = candle.close
        entity.volume = candle.volume
        entity.spread = candle.spread
        entity.ingested_at = ingested_at
        self.session.commit()
        return entity

    def get_all(self) -> list[MarketCandleEntity]:
        return self.session.query(MarketCandleEntity).all()

    def latest_time(self, source, symbol, timeframe):
        entity = (self.session.query(MarketCandleEntity)
                  .filter_by(source=source, symbol=symbol, timeframe=timeframe)
                  .order_by(MarketCandleEntity.candle_open_time.desc()).first())
        return entity.candle_open_time.replace(tzinfo=timezone.utc) if entity else None

    def recent(self, source, symbol, timeframe, limit):
        return list(reversed(self.session.query(MarketCandleEntity)
                    .filter_by(source=source, symbol=symbol, timeframe=timeframe)
                    .order_by(MarketCandleEntity.candle_open_time.desc()).limit(limit).all()))

    def upsert_batch(self, candles):
        """Commit a downloaded page atomically; failed pages cannot move the resume point."""
        if not candles:
            return 0
        first = candles[0]
        times = [item.candle_open_time.astimezone(timezone.utc).replace(tzinfo=None) for item in candles]
        existing = {}
        # Bootstrap windows can contain 5,000 rows. Keep IN queries under
        # SQLite's older bind-parameter limit as well as current versions.
        for offset in range(0, len(times), 500):
            rows = (self.session.query(MarketCandleEntity)
                    .filter_by(source=first.source, symbol=first.symbol, timeframe=first.timeframe)
                    .filter(MarketCandleEntity.candle_open_time.in_(times[offset:offset + 500])).all())
            existing.update({item.candle_open_time: item for item in rows})
        inserted = 0
        try:
            for candle, stamp in zip(candles, times):
                if (candle.source, candle.symbol, candle.timeframe) != (first.source, first.symbol, first.timeframe):
                    raise ValueError("A candle batch must belong to one source and market")
                entity = existing.get(stamp)
                if entity is None:
                    entity = MarketCandleEntity(source=candle.source, symbol=candle.symbol,
                                                timeframe=candle.timeframe, candle_open_time=stamp)
                    self.session.add(entity)
                    existing[stamp] = entity
                    inserted += 1
                for key in ("open", "high", "low", "close", "volume", "spread"):
                    setattr(entity, key, getattr(candle, key))
                entity.ingested_at = candle.ingested_at.astimezone(timezone.utc).replace(tzinfo=None)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return inserted
