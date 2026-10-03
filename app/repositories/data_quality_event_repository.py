import json
from datetime import timezone

from app.database.models import DataQualityEventEntity
from app.market_data.contracts import DataQualityEvent
from app.repositories.base_repository import BaseRepository


class DataQualityEventRepository(BaseRepository):
    def add(self, event: DataQualityEvent) -> DataQualityEventEntity:
        candle_time = None
        if event.candle_open_time is not None:
            candle_time = event.candle_open_time.astimezone(timezone.utc).replace(
                tzinfo=None
            )
        entity = DataQualityEventEntity(
            source=event.source,
            symbol=event.symbol,
            timeframe=event.timeframe,
            candle_open_time=candle_time,
            event_type=event.event_type,
            details_json=json.dumps(event.details, sort_keys=True),
        )
        self.session.add(entity)
        self.session.commit()
        return entity
