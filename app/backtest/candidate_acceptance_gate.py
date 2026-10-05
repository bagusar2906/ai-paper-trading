"""Read-only evidence gate for candidate-versus-champion backtests."""


class CandidateAcceptanceGate:
    """Summarise evidence for human review; this class never promotes a model."""

    MINIMUM_TRADES = 10

    def evaluate(self, candidate, champion) -> dict:
        candidate_trades = int(getattr(candidate, "total_trades", 0))
        champion_trades = int(getattr(champion, "total_trades", 0))
        candidate_profit = float(getattr(candidate, "net_profit", 0))
        champion_profit = float(getattr(champion, "net_profit", 0))
        candidate_drawdown = float(getattr(candidate, "max_drawdown", 0))
        champion_drawdown = float(getattr(champion, "max_drawdown", 0))
        candidate_factor = float(getattr(candidate, "profit_factor", 0))
        champion_factor = float(getattr(champion, "profit_factor", 0))

        checks = {
            "minimum_trades": candidate_trades >= self.MINIMUM_TRADES,
            "same_or_more_trades": candidate_trades >= champion_trades,
            "net_profit_not_worse": candidate_profit >= champion_profit,
            "drawdown_not_worse": candidate_drawdown <= champion_drawdown,
            "profit_factor_not_worse": candidate_factor >= champion_factor,
        }
        eligible_for_human_review = all(checks.values())
        return {
            "eligible_for_human_review": eligible_for_human_review,
            "recommendation": (
                "PROMOTE_FOR_HUMAN_REVIEW"
                if eligible_for_human_review
                else "RETRAIN_OR_INVESTIGATE"
            ),
            "automatic_promotion": False,
            "checks": checks,
            "reasons": [
                f"Candidate completed {candidate_trades} trades; minimum evidence is {self.MINIMUM_TRADES}.",
                f"Net profit difference versus champion: {candidate_profit - champion_profit:+.2f}.",
                f"Maximum drawdown difference versus champion: {candidate_drawdown - champion_drawdown:+.2f} (lower is better).",
            ],
        }
