"""Read-only recommendations for reviewing paper-trading model candidates."""

from __future__ import annotations

import json
from statistics import pstdev
from typing import Any


class ModelImprovementService:
    """Compare registered models without training, promoting, or trading them."""

    def build_report(self, models: list[Any]) -> dict:
        records = [self._record(model) for model in models]
        candidates = [record for record in records if record["status"] == "candidate"]
        assessments = [self._assess(candidate, records) for candidate in candidates]
        assessments.sort(key=self._rank_key)
        for rank, assessment in enumerate(assessments, start=1):
            assessment["rank"] = rank
        return {
            "paper_only": True,
            "automatic_promotion": False,
            "assessments": assessments,
        }

    @staticmethod
    def _rank_key(assessment: dict) -> tuple:
        """Prioritise reviewable, stronger, and more stable candidates first."""
        deltas = assessment["deltas"]
        stability = assessment["stability"]
        return (
            assessment["recommendation"] != "paper_test",
            assessment["champion_model_id"] is None,
            -(deltas.get("roc_auc") or 0),
            -(deltas.get("brier_score") or 0),
            stability["roc_auc_stddev"] if stability["roc_auc_stddev"] is not None else float("inf"),
            assessment["candidate_model_id"],
        )

    def _assess(self, candidate: dict, records: list[dict]) -> dict:
        champion = next(
            (
                model for model in records
                if model["status"] == "champion" and self._compatible(candidate, model)
            ),
            None,
        )
        deltas = self._metric_deltas(candidate["metrics"], champion["metrics"]) if champion else {}
        stability = self._fold_stability(candidate["metadata"])
        reasons = []
        if champion is None:
            reasons.append("No compatible champion exists for this feature set, label, and market context.")
        else:
            reasons.append(f"Compared with compatible champion {champion['model_id']}.")
            if deltas.get("roc_auc") is not None:
                direction = "improved" if deltas["roc_auc"] > 0 else "did not improve"
                reasons.append(f"ROC AUC {direction} by {deltas['roc_auc']:+.3f}.")
            if deltas.get("brier_score") is not None:
                direction = "improved" if deltas["brier_score"] > 0 else "did not improve"
                reasons.append(f"Brier score {direction} by {deltas['brier_score']:+.3f} (lower is better).")
        if stability["fold_count"] < 2:
            reasons.append("Only one validation fold is available; stability cannot be assessed.")
        elif stability["roc_auc_stddev"] is not None:
            reasons.append(f"Walk-forward ROC AUC standard deviation is {stability['roc_auc_stddev']:.3f}.")

        recommendation = "investigate"
        if champion is None:
            recommendation = "paper_test"
        elif (
            deltas.get("roc_auc", 0) > 0
            and deltas.get("brier_score", 0) >= 0
            and stability["fold_count"] >= 2
        ):
            recommendation = "paper_test"

        return {
            "candidate_model_id": candidate["model_id"],
            "champion_model_id": champion["model_id"] if champion else None,
            "comparison_available": champion is not None,
            "recommendation": recommendation,
            "deltas": deltas,
            "stability": stability,
            "reasons": reasons,
        }

    @staticmethod
    def _record(model: Any) -> dict:
        return {
            "model_id": model.model_id,
            "status": model.status,
            "feature_set_id": model.feature_set_id,
            "label_definition_id": model.label_definition_id,
            "metrics": ModelImprovementService._json_object(getattr(model, "metrics_json", "{}")),
            "metadata": ModelImprovementService._json_object(getattr(model, "metadata_json", "{}")),
        }

    @staticmethod
    def _compatible(left: dict, right: dict) -> bool:
        return (
            left["feature_set_id"] == right["feature_set_id"]
            and left["label_definition_id"] == right["label_definition_id"]
            and left["metadata"].get("market_context") == right["metadata"].get("market_context")
        )

    @staticmethod
    def _metric_deltas(candidate: dict, champion: dict) -> dict:
        # Positive values always mean that the candidate is better.
        return {
            "precision": ModelImprovementService._delta(candidate, champion, "precision"),
            "recall": ModelImprovementService._delta(candidate, champion, "recall"),
            "roc_auc": ModelImprovementService._delta(candidate, champion, "roc_auc"),
            "brier_score": ModelImprovementService._delta(champion, candidate, "brier_score"),
        }

    @staticmethod
    def _delta(left: dict, right: dict, key: str) -> float | None:
        first, second = left.get(key), right.get(key)
        if not isinstance(first, (int, float)) or not isinstance(second, (int, float)):
            return None
        return round(float(first) - float(second), 6)

    @staticmethod
    def _fold_stability(metadata: dict) -> dict:
        scores = [
            fold.get("metrics", {}).get("roc_auc")
            for fold in metadata.get("folds", [])
            if isinstance(fold, dict) and isinstance(fold.get("metrics", {}).get("roc_auc"), (int, float))
        ]
        return {
            "fold_count": len(scores),
            "roc_auc_stddev": round(pstdev(scores), 6) if len(scores) >= 2 else None,
        }

    @staticmethod
    def _json_object(value: str | dict) -> dict:
        if isinstance(value, dict):
            return value
        try:
            decoded = json.loads(value or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
