import json
from types import SimpleNamespace

from app.services.model_review_guidance_service import ModelReviewGuidanceService


def test_review_uses_local_evidence_when_no_ai_key(monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    model = SimpleNamespace(model_id="candidate-1", status="candidate", metrics_json=json.dumps({"roc_auc": 0.65, "brier_score": 0.2, "precision": 0.6, "recall": 0.5}), metadata_json=json.dumps({"folds": [{}, {}]}))
    result = ModelReviewGuidanceService().review(model)
    assert result["source"] == "local_evidence"
    assert result["automatic_promotion"] is False
    assert result["recommendation"] == "RUN_BACKTEST"
    assert "held-out backtest" in result["guidance"]
