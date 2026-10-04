"""Read-only feature-drift monitoring for the promoted paper-trading model."""

from __future__ import annotations

import json

import pandas as pd

from app.factories.provider_factory import create_provider
from app.factories.repository_factory import RepositoryFactory
from app.features.core_v1 import build_core_v1_features


class ModelHealthService:
    """Detect stale champion inputs; never retrain, promote, or execute trades."""

    DRIFT_THRESHOLD = 3.0

    def __init__(self, provider_factory=create_provider, repository_factory=RepositoryFactory):
        self.provider_factory = provider_factory
        self.repository_factory = repository_factory

    def check(self) -> dict:
        repos = self.repository_factory()
        try:
            champion = next((model for model in repos.model_registry.get_all() if model.status == "champion"), None)
        finally:
            repos.close()
        if champion is None:
            return {"status": "unavailable", "recommendation": "no_champion", "automatic_retraining": False, "reasons": ["No promoted champion model is available."]}
        metadata = self._metadata(champion.metadata_json)
        market = metadata.get("market_context") or {}
        if not market.get("symbol") or not market.get("timeframe") or not metadata.get("feature_baseline"):
            return {"status": "unavailable", "recommendation": "retrain_required", "automatic_retraining": False, "model_id": champion.model_id, "reasons": ["Champion lacks feature-baseline metadata; retrain it before drift monitoring."]}
        provider = self.provider_factory()
        try:
            candles = provider.get_history(market["symbol"], market["timeframe"], 300)
        finally:
            provider.disconnect()
        report = self.assess(metadata["feature_baseline"], build_core_v1_features(candles))
        return {"model_id": champion.model_id, "market_context": market, "automatic_retraining": False, **report}

    def assess(self, baseline: dict, features: pd.DataFrame) -> dict:
        recent = features.tail(50)
        drift = []
        for feature, values in baseline.items():
            if feature not in recent or not isinstance(values, dict):
                continue
            median, iqr = values.get("median"), values.get("iqr")
            if not isinstance(median, (int, float)) or not isinstance(iqr, (int, float)) or iqr <= 0:
                continue
            score = abs(float(recent[feature].median()) - median) / iqr
            drift.append({"feature": feature, "score": round(score, 3), "drifted": score >= self.DRIFT_THRESHOLD})
        drift.sort(key=lambda item: item["score"], reverse=True)
        count = sum(item["drifted"] for item in drift)
        status = "healthy" if count <= 1 else "watch" if count <= 5 else "stale"
        recommendation = "continue_monitoring" if status == "healthy" else "review_market_regime" if status == "watch" else "plan_retraining"
        return {
            "status": status,
            "recommendation": recommendation,
            "drifted_feature_count": count,
            "top_drift": drift[:5],
            "reasons": [f"{count} of {len(drift)} monitored features exceed the {self.DRIFT_THRESHOLD:g} IQR drift threshold."],
        }

    @staticmethod
    def _metadata(value: str) -> dict:
        try:
            decoded = json.loads(value or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
