from app.backtest.backtest_service import BacktestService


def _decision(action, probability, **gates):
    return {"action": action, "probability": probability, "gates": gates}


def test_decision_diagnostic_explains_identical_trades_with_different_probabilities():
    diagnostic = BacktestService._decision_disagreement(
        [_decision("HOLD", 0.72, long_probability=True), _decision("BUY", 0.81, long_probability=True)],
        [_decision("HOLD", 0.61), _decision("BUY", 0.79, long_probability=True)],
    )

    assert diagnostic["candles_evaluated"] == 2
    assert diagnostic["decision_disagreements"] == 0
    assert diagnostic["rule_blocked_disagreements"] == 1
    assert diagnostic["average_probability_difference"] > 0
    assert "same final decision" in diagnostic["summary"]


def test_decision_diagnostic_counts_different_final_actions():
    diagnostic = BacktestService._decision_disagreement(
        [_decision("BUY", 0.80, long_probability=True)],
        [_decision("HOLD", 0.50)],
    )

    assert diagnostic["decision_disagreements"] == 1
    assert diagnostic["rule_blocked_disagreements"] == 0
