from app.database.models import TradeEntity
from app.models.trade import Trade


class TradeMapper:

    @staticmethod
    def to_entity(trade: Trade):

        return TradeEntity(
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            pnl=trade.pnl,
            opened_at=trade.opened_at,
            closed_at=trade.closed_at,
        )

    @staticmethod
    def to_domain(entity: TradeEntity):

        trade = Trade(
            symbol=entity.symbol,
            side=entity.side,
            quantity=entity.quantity,
            entry_price=entity.entry_price,
            exit_price=entity.exit_price,
            pnl=entity.pnl,
            opened_at=entity.opened_at,
            closed_at=entity.closed_at,
        )

        trade.id = entity.id

        return trade