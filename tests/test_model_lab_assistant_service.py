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


def test_assistant_explains_all_model_lab_buttons_from_its_capability_guide():
    response = ModelLabAssistantService().respond("What does every button do?", [])

    assert "Train Candidate" in response["answer"]
    assert "Get AI review guidance" in response["answer"]
    assert "Champions cannot be deleted" in response["answer"]


def test_assistant_uses_configured_openai_compatible_gateway(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"output_text": '{"answer":"Compare it with a held-out backtest, then ask a human reviewer."}'}

    captured = {}

    def request(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_API_BASE_URL", "http://127.0.0.1:20128/v1")
    monkeypatch.setenv("OPENAI_TRADING_MODEL", "my-combo")

    response = ModelLabAssistantService(requester=request).respond("Compare candidate", [_model("btc", "candidate")])

    assert response["source"] == "omniroute"
    assert captured["url"] == "http://127.0.0.1:20128/v1/responses"
    assert captured["json"]["model"] == "my-combo"
    assert captured["json"]["store"] is False
    assert captured["json"]["input"].find("model_lab_capabilities") >= 0
