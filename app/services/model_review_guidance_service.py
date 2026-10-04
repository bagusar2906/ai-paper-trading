"""Optional AI guidance for model review; it cannot change model state."""

from __future__ import annotations

import json
import os

import requests


class ModelReviewGuidanceService:
    RESPONSE_SCHEMA = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "recommendation": {"type": "string", "enum": ["PROMOTE_FOR_HUMAN_REVIEW", "RUN_BACKTEST", "RETRAIN_OR_INVESTIGATE"]},
            "guidance": {"type": "string"},
        },
        "required": ["recommendation", "guidance"],
    }
    def __init__(self, requester=requests.post):
        self.requester = requester
        self.api_key = os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        self.api_base_url = os.environ.get("AI_API_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.environ.get("OPENAI_TRADING_MODEL", "gpt-5-mini")

    def review(self, model) -> dict:
        evidence = self._evidence(model)
        if not self.api_key:
            return self._local_response(evidence)
        try:
            response = self.requester(f"{self.api_base_url}/responses", headers={"Authorization": f"Bearer {self.api_key}"}, json={"model": self.model, "store": False, "instructions": "You are a cautious ML review assistant. Review only supplied evidence. Recommend one next step, but never claim the model was promoted or should trade live.", "input": json.dumps(evidence), "text": {"format": {"type": "json_schema", "name": "model_review", "strict": True, "schema": self.RESPONSE_SCHEMA}}}, timeout=20)
            response.raise_for_status()
            result = json.loads(self._response_text(response.json()))
            return {"source": "ai", "recommendation": result["recommendation"], "guidance": result["guidance"], "automatic_promotion": False}
        except (requests.RequestException, ValueError, KeyError):
            return self._local_response(evidence)

    @staticmethod
    def _evidence(model) -> dict:
        try: metadata = json.loads(model.metadata_json or "{}")
        except (TypeError, json.JSONDecodeError): metadata = {}
        try: metrics = json.loads(model.metrics_json or "{}")
        except (TypeError, json.JSONDecodeError): metrics = {}
        return {"model_id": model.model_id, "status": model.status, "validation_metrics": {key: metrics.get(key) for key in ("precision", "recall", "roc_auc", "brier_score")}, "fold_count": len(metadata.get("folds", [])), "top_features": metadata.get("feature_importance", [])[:5]}

    @staticmethod
    def _local_response(evidence: dict) -> dict:
        metrics = evidence["validation_metrics"]
        if not all(isinstance(value, (int, float)) for value in metrics.values()):
            return {"source": "local_evidence", "recommendation": "RETRAIN_OR_INVESTIGATE", "guidance": "Validation evidence is incomplete. Retrain or investigate before considering promotion.", "automatic_promotion": False}
        recommendation = "RUN_BACKTEST" if metrics["roc_auc"] >= 0.55 and metrics["brier_score"] <= 0.25 and evidence["fold_count"] >= 2 else "RETRAIN_OR_INVESTIGATE"
        return {"source": "local_evidence", "recommendation": recommendation, "guidance": f"Inspect {evidence['fold_count']} walk-forward folds, ROC AUC {metrics['roc_auc']:.3f}, and Brier score {metrics['brier_score']:.3f}. Compare with the champion in a held-out backtest before manual promotion.", "automatic_promotion": False}

    @staticmethod
    def _response_text(payload: dict) -> str:
        if payload.get("output_text"): return str(payload["output_text"])
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text": return str(content.get("text", ""))
        raise ValueError("Responses API returned no review text")
