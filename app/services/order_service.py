import logging
from datetime import datetime, timezone

from app.brokers.paper_broker import PaperBroker
from app.config import TradingConfig
from app.enums.signal_action import SignalAction
from app.models.dashboard.order_request import OrderRequest
from app.models.signal import TradingSignal
from app.services.order_response import OrderResponse

logger = logging.getLogger(__name__)


class OrderService:

    def place_order(self, request: OrderRequest) -> OrderResponse:

        if request.action not in (SignalAction.BUY, SignalAction.SELL):
            return OrderResponse(
                success=False,
                message=f"Invalid order action: {request.action}",
            )

        if request.quantity <= 0:
            return OrderResponse(
                success=False,
                message="Quantity must be greater than zero.",
            )

        broker = PaperBroker(initial_balance=TradingConfig.INITIAL_BALANCE)

        try:
            existing = broker.repos.positions.get_by_symbol(request.symbol)

            if existing is not None:
                return OrderResponse(
                    success=False,
                    message=f"A position already exists for {request.symbol}.",
                )

            signal = TradingSignal(
                symbol=request.symbol,
                action=request.action,
                price=request.price,
                quantity=request.quantity,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                confidence=1.0,
                reason="Manual order",
                time=datetime.now(timezone.utc),
            )

            broker.execute(signal)

            # Manual orders are explicit user actions, so always record them
            # in signal history / chart markers (no consecutive-dup dedup).
            broker.repos.signals.add(signal)

            logger.info(
                "Manual order placed: %s %s %.2f @ %.2f",
                signal.action,
                signal.symbol,
                signal.quantity,
                signal.price,
            )

            return OrderResponse(
                success=True,
                message=f"{signal.action} order placed for {signal.symbol}.",
            )

        except Exception as exc:
            logger.exception("Failed to place manual order")
            return OrderResponse(
                success=False,
                message=f"Unable to place order: {exc}",
            )

        finally:
            broker.close()
