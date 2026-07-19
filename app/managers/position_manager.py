import logging

from app.brokers.paper_broker import PaperBroker
from app.enums.signal_action import SignalAction

logger = logging.getLogger(__name__)


class PositionManager:

    def __init__(self, broker: PaperBroker):
        self.broker = broker

    def update(self, current_price: float):

        positions = self.broker.get_positions()

        for position in positions.copy():

            #
            # BUY Position
            #

            if position.side == SignalAction.BUY:

                if (
                    position.take_profit is not None
                    and current_price >= position.take_profit
                ):
                    logger.info(
                        "Take Profit hit for %s",
                        position.symbol,
                    )

                    self.broker.close_position(
                        position.symbol,
                        current_price,
                    )

                    continue

                if (
                    position.stop_loss is not None
                    and current_price <= position.stop_loss
                ):
                    logger.info(
                        "Stop Loss hit for %s",
                        position.symbol,
                    )

                    self.broker.close_position(
                        position.symbol,
                        current_price,
                    )

            #
            # SELL Position
            #

            elif position.side == SignalAction.SELL:

                if (
                    position.take_profit is not None
                    and current_price <= position.take_profit
                ):
                    logger.info(
                        "Take Profit hit for %s",
                        position.symbol,
                    )

                    self.broker.close_position(
                        position.symbol,
                        current_price,
                    )

                    continue

                if (
                    position.stop_loss is not None
                    and current_price >= position.stop_loss
                ):
                    logger.info(
                        "Stop Loss hit for %s",
                        position.symbol,
                    )

                    self.broker.close_position(
                        position.symbol,
                        current_price,
                    )