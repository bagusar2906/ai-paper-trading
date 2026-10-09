from datetime import timezone

from app.database.models import TradingCheckpointEntity
from app.repositories.base_repository import BaseRepository, commit_or_flush


class TradingCheckpointRepository(BaseRepository):
    def get(self, source, symbol, timeframe):
        return self.session.get(TradingCheckpointEntity, (source, symbol, timeframe))

    def save(self, source, symbol, timeframe, candle_time, history_json):
        entity = self.get(source, symbol, timeframe)
        if entity is None:
            entity = TradingCheckpointEntity(source=source, symbol=symbol, timeframe=timeframe)
            self.session.add(entity)
        entity.candle_time = candle_time.astimezone(timezone.utc).replace(tzinfo=None)
        entity.history_json = history_json
        commit_or_flush(self.session)
