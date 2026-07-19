
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

    def get_all(self):

        return self.session.query(SignalEntity).all()

    def get_last(self, symbol):

        return (
            self.session.query(SignalEntity)
            .filter_by(symbol=symbol)
            .order_by(SignalEntity.created_at.desc())
            .first()
        )
    
    def get_recent(self, limit=200):

        entities = (
            self.session.query(SignalEntity)
            .order_by(SignalEntity.created_at.desc())
            .limit(limit)
            .all()
        )

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
            for e in entities
        ]))