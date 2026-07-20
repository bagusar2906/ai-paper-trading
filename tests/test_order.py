from datetime import datetime

import pytest

from app.enums.signal_action import SignalAction
from app.models.position.order_request import OrderRequest
from app.services.order_service import OrderService


def _order(**overrides):

    defaults = {
        "symbol": "XAUUSD",
        "action": SignalAction.BUY,
        "price": 3375.50,
        "quantity": 1.0,
        "stop_loss": 3370.50,
        "take_profit": 3385.50,
    }

    defaults.update(overrides)

    return OrderRequest(**defaults)


# =============================================================================
# Successful orders
# =============================================================================

def test_place_buy_order_opens_a_position():

    service = OrderService()

    result = service.place_order(_order())

    assert result.success is True

    from app.brokers.paper_broker import PaperBroker
    from app.config import TradingConfig

    broker = PaperBroker(initial_balance=TradingConfig.INITIAL_BALANCE)

    try:
        positions = broker.get_positions()

        assert len(positions) == 1
        assert positions[0].symbol == "XAUUSD"
        assert positions[0].side == SignalAction.BUY
        assert positions[0].entry_price == 3375.50
        assert positions[0].stop_loss == 3370.50
        assert positions[0].take_profit == 3385.50
    finally:
        broker.close()


def test_place_sell_order_opens_a_position():

    service = OrderService()

    result = service.place_order(
        _order(
            action=SignalAction.SELL,
            price=3400.0,
            stop_loss=3410.0,
            take_profit=3380.0,
        )
    )

    assert result.success is True

    from app.brokers.paper_broker import PaperBroker
    from app.config import TradingConfig

    broker = PaperBroker(initial_balance=TradingConfig.INITIAL_BALANCE)

    try:
        positions = broker.get_positions()
        assert len(positions) == 1
        assert positions[0].side == SignalAction.SELL
    finally:
        broker.close()


def test_manual_order_is_recorded_in_signal_history():

    service = OrderService()

    service.place_order(_order())

    from app.brokers.paper_broker import PaperBroker
    from app.config import TradingConfig

    broker = PaperBroker(initial_balance=TradingConfig.INITIAL_BALANCE)

    try:
        signals = broker.repos.signals.get_recent(10)
        assert len(signals) == 1
        assert signals[0].action == "BUY"
        assert signals[0].reason == "Manual order"
    finally:
        broker.close()


# =============================================================================
# Validation failures (should not raise, should return success=False)
# =============================================================================

def test_place_order_rejects_zero_quantity():

    service = OrderService()

    result = service.place_order(_order(quantity=0))

    assert result.success is False
    assert "quantity" in result.message.lower()


def test_place_order_rejects_negative_quantity():

    service = OrderService()

    result = service.place_order(_order(quantity=-1))

    assert result.success is False


def test_place_order_rejects_hold_action():

    service = OrderService()

    result = service.place_order(_order(action=SignalAction.HOLD))

    assert result.success is False


def test_duplicate_order_for_open_symbol_is_rejected():

    service = OrderService()

    first = service.place_order(_order())
    second = service.place_order(_order())

    assert first.success is True
    assert second.success is False
    assert "already exists" in second.message.lower()

    from app.brokers.paper_broker import PaperBroker
    from app.config import TradingConfig

    broker = PaperBroker(initial_balance=TradingConfig.INITIAL_BALANCE)

    try:
        assert len(broker.get_positions()) == 1
    finally:
        broker.close()
