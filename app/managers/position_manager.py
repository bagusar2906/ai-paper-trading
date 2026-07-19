import logging

from app.brokers.paper_broker import PaperBroker
from app.enums.signal_action import SignalAction

logger = logging.getLogger(__name__)


class PositionManager:

    def __init__(self, broker: PaperBroker):
        self.broker = broker

    def update(
        self,
        symbol: str,
        current_price: float,
    ):
        """
        Check all open positions for the given symbol.

        Returns:
            list[Trade]: Closed trades.
        """

        closed_trades = []

        positions = self.broker.get_positions()

        for position in positions.copy():

            if position.symbol != symbol:
                continue

            #
            # BUY Position
            #

            if position.side == SignalAction.BUY:

                #
                # Take Profit
                #

                if (
                    position.take_profit is not None
                    and current_price >= position.take_profit
                ):

                    logger.info(
                        "BUY TP hit: %s @ %.2f",
                        position.symbol,
                        current_price,
                    )

                    trade = self.broker.close_position(
                        position.symbol,
                        current_price,
                    )

                    if trade:
                        closed_trades.append(trade)

                    continue

                #
                # Stop Loss
                #

                if (
                    position.stop_loss is not None
                    and current_price <= position.stop_loss
                ):

                    logger.info(
                        "BUY SL hit: %s @ %.2f",
                        position.symbol,
                        current_price,
                    )

                    trade = self.broker.close_position(
                        position.symbol,
                        current_price,
                    )

                    if trade:
                        closed_trades.append(trade)

            #
            # SELL Position
            #

            elif position.side == SignalAction.SELL:

                #
                # Take Profit
                #

                if (
                    position.take_profit is not None
                    and current_price <= position.take_profit
                ):

                    logger.info(
                        "SELL TP hit: %s @ %.2f",
                        position.symbol,
                        current_price,
                    )

                    trade = self.broker.close_position(
                        position.symbol,
                        current_price,
                    )

                    if trade:
                        closed_trades.append(trade)

                    continue

                #
                # Stop Loss
                #

                if (
                    position.stop_loss is not None
                    and current_price >= position.stop_loss
                ):

                    logger.info(
                        "SELL SL hit: %s @ %.2f",
                        position.symbol,
                        current_price,
                    )

                    trade = self.broker.close_position(
                        position.symbol,
                        current_price,
                    )

                    if trade:
                        closed_trades.append(trade)

        return closed_trades