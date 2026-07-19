from app.models.position import Position
from app.database.models import PositionEntity


class PositionMapper:

    @staticmethod
    def to_entity(position: Position) -> PositionEntity:

        return PositionEntity(
            symbol=position.symbol,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            opened_at=position.opened_at,
        )

    @staticmethod
    def to_domain(entity: PositionEntity) -> Position:

        return Position(
            symbol=entity.symbol,
            side=entity.side,
            quantity=entity.quantity,
            entry_price=entity.entry_price,
            stop_loss=entity.stop_loss,
            take_profit=entity.take_profit,
            opened_at=entity.opened_at,
        )