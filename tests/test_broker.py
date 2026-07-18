from datetime import datetime

from app.enums.signal_action import SignalAction
import pytest

from app.brokers.paper_broker import PaperBroker
from app.models.account import Account
from app.models.position import Position
from app.models.signal import TradingSignal
from app.models.trade import Trade


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def broker():
    return PaperBroker(initial_balance=10_000)


# =============================================================================
# Helpers
# =============================================================================

def _signal(**overrides):

    defaults = {
        "symbol": "XAUUSD",
        "action": SignalAction.BUY,
        "price": 3375.50,
        "time": datetime.now(),
        "stop_loss": 3370.50,
        "take_profit": 3385.50,
        "reason": "EMA crossed above trend",
        "confidence": 0.95,
    }

    defaults.update(overrides)

    return TradingSignal(**defaults)


# =============================================================================
# Account
# =============================================================================

def test_initial_account_matches_starting_balance(broker):

    account = broker.get_account()

    assert isinstance(account, Account)

    assert account.balance == 10_000
    assert account.equity == 10_000
    assert account.margin == 0.0
    assert account.free_margin == 10_000
    assert account.floating_pnl == 0.0

    assert broker.get_positions() == []
    assert broker.get_trades() == []


# =============================================================================
# BUY
# =============================================================================

def test_execute_buy_signal_opens_position(broker):

    signal = _signal()

    broker.execute(signal)

    positions = broker.get_positions()

    assert len(positions) == 1

    position = positions[0]

    assert isinstance(position, Position)

    assert position.symbol == signal.symbol
    assert position.side == SignalAction.BUY
    assert position.quantity == 1.0
    assert position.entry_price == signal.price
    assert position.stop_loss == signal.stop_loss
    assert position.take_profit == signal.take_profit

    account = broker.get_account()

    # Opening a position should not change balance
    assert account.balance == 10_000
    assert account.equity == 10_000


# =============================================================================
# SELL
# =============================================================================

def test_execute_sell_signal_opens_position(broker):

    signal = _signal(
        action=SignalAction.SELL,
        price=3400.0,
        stop_loss=3410.0,
        take_profit=3380.0,
    )

    broker.execute(signal)

    positions = broker.get_positions()

    assert len(positions) == 1

    position = positions[0]

    assert position.side == SignalAction.SELL
    assert position.stop_loss == signal.stop_loss
    assert position.take_profit == signal.take_profit


# =============================================================================
# HOLD
# =============================================================================

def test_execute_hold_signal_does_not_open_position(broker):

    signal = _signal(action=SignalAction.HOLD)

    broker.execute(signal)

    assert broker.get_positions() == []


# =============================================================================
# Invalid Action
# =============================================================================

def test_invalid_signal_does_not_open_position(broker):

    signal = _signal(action=SignalAction.HOLD)  # Using HOLD as a placeholder for an invalid action

    broker.execute(signal)

    assert broker.get_positions() == []


# =============================================================================
# Duplicate Position
# =============================================================================

def test_duplicate_position_is_ignored(broker):

    broker.execute(_signal())

    broker.execute(_signal())

    assert len(broker.get_positions()) == 1


# =============================================================================
# Multiple Symbols
# =============================================================================

def test_multiple_symbols_can_be_open(broker):

    broker.execute(
        _signal(
            symbol="XAUUSD"
        )
    )

    broker.execute(
        _signal(
            symbol="EURUSD",
            action=SignalAction.SELL,
            price=1.1700,
            stop_loss=1.1750,
            take_profit=1.1600,
        )
    )

    positions = broker.get_positions()

    assert len(positions) == 2

    assert positions[0].symbol == "XAUUSD"
    assert positions[1].symbol == "EURUSD"


# =============================================================================
# Close Position
# =============================================================================

def test_close_buy_position(broker):

    broker.execute(_signal())

    trade = broker.close_position(
        "XAUUSD",
        3380.50
    )

    assert isinstance(trade, Trade)

    assert len(broker.get_positions()) == 0
    assert len(broker.get_trades()) == 1


# =============================================================================
# Profit
# =============================================================================

def test_buy_profit_updates_balance(broker):

    broker.execute(_signal())

    broker.close_position(
        "XAUUSD",
        3380.50
    )

    account = broker.get_account()

    assert account.balance == 10005.0


def test_buy_loss_updates_balance(broker):

    broker.execute(_signal())

    broker.close_position(
        "XAUUSD",
        3370.50
    )

    account = broker.get_account()

    assert account.balance == 9995.0


def test_sell_profit_updates_balance(broker):

    broker.execute(
        _signal(
            action=SignalAction.SELL,
            price=3400.0
        )
    )

    broker.close_position(
        "XAUUSD",
        3390.0
    )

    account = broker.get_account()

    assert account.balance == 10010.0


def test_sell_loss_updates_balance(broker):

    broker.execute(
        _signal(
            action=SignalAction.SELL,
            price=3400.0
        )
    )

    broker.close_position(
        "XAUUSD",
        3410.0
    )

    account = broker.get_account()

    assert account.balance == 9990.0