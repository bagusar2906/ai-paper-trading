
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
            time=signal.time,
        )

        self.session.add(entity)
        self.session.commit()

    def get_all(self):

        return self.session.query(SignalEntity).all()
    
    def get_recent(self, limit: int = 20):

            entities = (
                self.session.query(SignalEntity)
                .order_by(SignalEntity.created_at.desc())
                .limit(limit)
                .all()
            )

            return [
                TradingSignal(
                    symbol=e.symbol,
                    action=e.action,
                    price=e.price,
                    stop_loss=e.stop_loss,
                    take_profit=e.take_profit,
                    reason=e.reason,
                    confidence=e.confidence,
                    time=e.time,
                )
                for e in entities
            ]