
from app.database.models import SignalEntity
from app.models.signal import TradingSignal
from app.repositories.base_repository import BaseRepository


class SignalRepository(BaseRepository):

    def add(self, signal: TradingSignal):

        entity = SignalEntity(
            symbol=signal.symbol,
            action=signal.action,
            price=signal.price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            reason=signal.reason,
            confidence=signal.confidence,
            signal_time=signal.time,
        )

        self.session.add(entity)
        self.session.commit()

    def upsert_for_candle(self, signal: TradingSignal):
        """Store one current signal for a symbol on a specific candle.

        The scheduler polls more frequently than the market timeframe.  An AI
        decision can change between polls even when the final candle timestamp
        has not changed, so action-based deduplication is insufficient.  The
        candle timestamp is the history key; a later decision replaces the
        earlier one rather than creating a second history row.
        """
        matching = (
            self.session.query(SignalEntity)
            .filter_by(symbol=signal.symbol, signal_time=signal.time)
            .order_by(SignalEntity.id.desc())
            .all()
        )

        if matching:
            entity = matching[0]
            for duplicate in matching[1:]:
                self.session.delete(duplicate)
        else:
            entity = SignalEntity(
                symbol=signal.symbol,
                signal_time=signal.time,
            )
            self.session.add(entity)

        entity.action = signal.action
        entity.price = signal.price
        entity.stop_loss = signal.stop_loss
        entity.take_profit = signal.take_profit
        entity.reason = signal.reason
        entity.confidence = signal.confidence

        self.session.commit()
        return entity

    def get_all(self):

        return self.session.query(SignalEntity).all()

    def get_last(self, symbol):

        return (
            self.session.query(SignalEntity)
            .filter_by(symbol=symbol)
            .order_by(SignalEntity.created_at.desc(), SignalEntity.id.desc())
            .first()
        )
    
    def get_recent(self, limit=200):

        entities = (
            self.session.query(SignalEntity)
            .order_by(SignalEntity.created_at.desc(), SignalEntity.id.desc())
            .limit(limit)
            .all()
        )

        # Existing databases can contain duplicate rows written before candle
        # upserts were introduced. Show only the newest record for each candle
        # while new writes also clean duplicates proactively.
        unique_entities = []
        seen = set()
        for entity in entities:
            key = (entity.symbol, entity.signal_time)
            if key in seen:
                continue
            seen.add(key)
            unique_entities.append(entity)

        return list(reversed([
            TradingSignal(
                symbol=e.symbol,
                action=e.action,
                price=e.price,
                time=e.signal_time,
                confidence=e.confidence,
                reason=e.reason,
                stop_loss=e.stop_loss,
                take_profit=e.take_profit,
            )
            for e in unique_entities
        ]))
