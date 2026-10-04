from types import SimpleNamespace

from app.backtest.candidate_acceptance_gate import CandidateAcceptanceGate


def _statistics(trades, profit, drawdown, profit_factor):
    return SimpleNamespace(
        total_trades=trades,
        net_profit=profit,
        max_drawdown=drawdown,
        profit_factor=profit_factor,
    )


def test_gate_allows_human_review_only_when_candidate_meets_all_evidence_checks():
    candidate = _statistics(12, 120, 30, 1.4)
    champion = _statistics(10, 100, 35, 1.2)

    result = CandidateAcceptanceGate().evaluate(candidate, champion)

    assert result["eligible_for_human_review"] is True
    assert result["automatic_promotion"] is False


def test_gate_rejects_insufficient_or_worse_candidate_evidence():
    candidate = _statistics(4, 90, 40, 1.1)
    champion = _statistics(10, 100, 35, 1.2)

    result = CandidateAcceptanceGate().evaluate(candidate, champion)

    assert result["eligible_for_human_review"] is False
    assert result["checks"]["minimum_trades"] is False
    assert result["checks"]["drawdown_not_worse"] is False
