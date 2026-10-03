from app.models.dashboard.signal_response import SignalResponse


def test_signal_response_exposes_stop_loss_and_take_profit():
    signal = SignalResponse(
        symbol="XAUUSD",
        action="BUY",
        price=2000.0,
        confidence=0.72,
        stop_loss=1995.0,
        take_profit=2010.0,
        quantity=None,
        reason="test",
        time=None,
        risk_reward=2.0,
    )

    assert signal.stop_loss == 1995.0
    assert signal.take_profit == 2010.0
