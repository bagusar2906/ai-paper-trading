import datetime

from app.models.dashboard.order_request import OrderRequest
from app.models.signal import TradingSignal
from tests.test_broker import broker
from tests.test_broker import broker


class OrderService:

    def place_order(self, request: OrderRequest):

        signal = TradingSignal(
            symbol=request.symbol,
            action=request.action,
            price=request.price,
            quantity=request.quantity,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            confidence=100,
            reason="Manual Order",
            time=datetime.utcnow(),
        )

        broker.execute(signal)