from datetime import datetime

from app.analytics.performance_tracker import PerformanceTracker
from app.enums.signal_action import SignalAction
from app.models.trade import Trade


def trade(pnl):

    return Trade(
        id=None,
        symbol="XAUUSD",
        side=SignalAction.BUY,
        quantity=1,
        entry_price=100,
        exit_price=101,
        pnl=pnl,
        opened_at=datetime.now(),
        closed_at=datetime.now(),
    )


def test_empty_trade_list():

    tracker = PerformanceTracker()

    stats = tracker.calculate([])

    assert stats.total_trades == 0
    assert stats.net_profit == 0


def test_statistics():

    tracker = PerformanceTracker()

    trades = [
        trade(10),
        trade(20),
        trade(-5),
        trade(-15),
        trade(0),
    ]

    stats = tracker.calculate(trades)

    assert stats.total_trades == 5
    assert stats.winning_trades == 2
    assert stats.losing_trades == 2
    assert stats.breakeven_trades == 1

    assert stats.gross_profit == 30
    assert stats.gross_loss == 20
    assert stats.net_profit == 10

    assert stats.win_rate == 40.0
    assert stats.profit_factor == 1.5

    assert stats.average_win == 15
    assert stats.average_loss == -10

    assert stats.largest_win == 20
    assert stats.largest_loss == -15