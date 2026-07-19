from app.brokers.paper_broker import PaperBroker


class PositionManager:

    def __init__(self, broker: PaperBroker):

        self.broker = broker

    def update(self, current_price: float):

        positions = self.broker.get_positions()

        for position in positions:

            #
            # BUY
            #

            if position.side == "BUY":

                if (
                    position.take_profit is not None
                    and current_price >= position.take_profit
                ):

                    self.broker.close_position(
                        position.symbol,
                        current_price,
                    )

                    continue

                if (
                    position.stop_loss is not None
                    and current_price <= position.stop_loss
                ):

                    self.broker.close_position(
                        position.symbol,
                        current_price,
                    )

            #
            # SELL
            #

            else:

                if (
                    position.take_profit is not None
                    and current_price <= position.take_profit
                ):

                    self.broker.close_position(
                        position.symbol,
                        current_price,
                    )

                    continue

                if (
                    position.stop_loss is not None
                    and current_price >= position.stop_loss
                ):

                    self.broker.close_position(
                        position.symbol,
                        current_price,
                    )