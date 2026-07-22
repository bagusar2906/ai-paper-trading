from datetime import datetime

import pytest


from app.brokers.backtest_broker import BacktestBroker
from app.models.signal import TradingSignal, SignalAction


def create_buy_signal(
    price=1.1000,
    quantity=1000,
):
    return TradingSignal(
        symbol="EURUSD",
        action=SignalAction.BUY,
        quantity=quantity,
        price=price,
        stop_loss=1.0900,
        take_profit=1.1200,
        time=datetime(2026, 7, 22),
    )


def test_update_market_price_updates_equity_and_records_history():

    broker = BacktestBroker(initial_balance=10000)

    signal = create_buy_signal()

    broker.execute(signal)

    broker.update_market_price(
        "EURUSD",
        1.1050,
    )

    account = broker.get_account()

    expected_pnl = (1.1050 - 1.1000) * 1000

    assert account.floating_pnl == pytest.approx(expected_pnl)

    assert account.equity == pytest.approx(
        10000 + expected_pnl
    )

    assert len(broker.equity_history) == 1

    point = broker.equity_history[0]

    assert point["equity"] == pytest.approx(
        account.equity
    )


def test_update_market_price_multiple_times_records_multiple_points():

    broker = BacktestBroker(initial_balance=10000)

    broker.execute(create_buy_signal())

    broker.update_market_price(
        "EURUSD",
        1.1010,
    )

    broker.update_market_price(
        "EURUSD",
        1.1020,
    )

    broker.update_market_price(
        "EURUSD",
        1.1030,
    )

    assert len(broker.equity_history) == 3

    assert broker.equity_history[0]["equity"] < broker.equity_history[1]["equity"]

    assert broker.equity_history[1]["equity"] < broker.equity_history[2]["equity"]


def test_update_market_price_without_position_keeps_equity_constant():

    broker = BacktestBroker(initial_balance=10000)

    broker.update_market_price(
        "EURUSD",
        1.1000,
    )

    account = broker.get_account()

    assert account.balance == 10000

    assert account.equity == 10000

    assert account.floating_pnl == 0

    assert len(broker.equity_history) == 1

    assert broker.equity_history[0]["equity"] == 10000