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
