from datetime import datetime

import pytest

from app.brokers.paper_broker import PaperBroker
from app.models.signal import TradingSignal
from app.models.account import Account
from app.models.position import Position


def _buy_signal(**overrides):
    defaults = dict(
        symbol="XAUUSD",
        action="BUY",
        price=3375.50,
        time=datetime.now(),
        stop_loss=3370.50,
        take_profit=3385.50,
        reason="EMA crossed above trend",
        confidence=0.95,
    )
    defaults.update(overrides)
    return TradingSignal(**defaults)


def test_initial_account_matches_starting_balance():
    broker = PaperBroker(initial_balance=10_000)
    account = broker.get_account()

    assert isinstance(account, Account)
    assert account.balance == 10_000
    assert account.equity == 10_000
    assert account.margin == 0.0
    assert account.free_margin == 10_000
    assert account.floating_pnl == 0.0
    assert broker.get_positions() == []


def test_execute_buy_signal_opens_a_position():
    broker = PaperBroker(initial_balance=10_000)
    signal = _buy_signal()

    broker.execute(signal)
    positions = broker.get_positions()

    assert len(positions) == 1
    position = positions[0]
    assert isinstance(position, Position)
    assert position.symbol == "XAUUSD"
    assert position.side == "BUY"
    assert position.entry_price == signal.price
    assert position.stop_loss == signal.stop_loss
    assert position.take_profit == signal.take_profit


def test_execute_sell_signal_opens_a_position():
    broker = PaperBroker(initial_balance=10_000)
    signal = _buy_signal(action="SELL", price=3400.0)

    broker.execute(signal)
    positions = broker.get_positions()

    assert len(positions) == 1
    assert positions[0].side == "SELL"


def test_execute_hold_signal_does_not_open_a_position():
    broker = PaperBroker(initial_balance=10_000)
    signal = _buy_signal(action="HOLD")

    broker.execute(signal)

    assert broker.get_positions() == []


def test_execute_multiple_signals_accumulates_positions():
    broker = PaperBroker(initial_balance=10_000)

    broker.execute(_buy_signal(action="BUY"))
    broker.execute(_buy_signal(action="SELL"))

    assert len(broker.get_positions()) == 2


def test_close_position_not_yet_implemented():
    # Documents a known limitation rather than hiding it: PaperBroker.execute()
    # can open positions but closing them isn't implemented yet.
    broker = PaperBroker(initial_balance=10_000)
    broker.execute(_buy_signal())

    with pytest.raises(NotImplementedError):
        broker.close_position("XAUUSD", price=3380.0)
