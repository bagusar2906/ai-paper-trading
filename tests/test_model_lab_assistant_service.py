import json

from app.database.models import ModelVersionEntity
from app.services.model_lab_assistant_service import ModelLabAssistantService


def _model(model_id, status, symbol="BTC/USDT", timeframe="1h"):
    return ModelVersionEntity(
        model_id=model_id, training_run_id=f"run-{model_id}", status=status,
        artifact_path="artifact.pkl", artifact_sha256="a" * 64,
        feature_set_id="core-v1", label_definition_id="label-v1", metrics_json="{}",
        metadata_json=json.dumps({"market_context": {"symbol": symbol, "timeframe": timeframe}}),
    )


def test_assistant_explains_context_safe_candidate_comparison():
    response = ModelLabAssistantService().respond(
        "Compare candidate models", [_model("btc", "candidate")]
    )

    assert "same symbol and timeframe" in response["answer"]
    assert response["automatic_actions"] is False


def test_assistant_explains_retraining_without_actioning_it():
    response = ModelLabAssistantService().respond(
        "Why retrain?", [_model("eth", "champion", "ETH/USDT", "4h")]
    )

    assert "candidate-only" in response["answer"]
    assert response["available_actions"] == ["train_candidate", "run_held_out_backtest", "manual_promotion_review"]
