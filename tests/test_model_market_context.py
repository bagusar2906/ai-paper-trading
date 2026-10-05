import json

from app.database.models import ModelVersionEntity


def _model(model_id, status, symbol, timeframe):
    return ModelVersionEntity(
        model_id=model_id,
        training_run_id=f"training-{model_id}",
        status=status,
        artifact_path=f"data/model_artifacts/{model_id}.pkl",
        artifact_sha256="a" * 64,
        feature_set_id="core-v1",
        label_definition_id="future-return-up",
        metrics_json="{}",
        metadata_json=json.dumps({"market_context": {
            "symbol": symbol,
            "timeframe": timeframe,
        }}),
    )


def test_champions_are_selected_by_symbol_and_timeframe(repos):
    btc = _model("btc-champion", "champion", "BTC/USDT", "1h")
    eth = _model("eth-champion", "champion", "ETH/USDT", "1h")
    repos.session.add_all([btc, eth])
    repos.session.commit()

    selected = repos.model_registry.get_champion(
        "core-v1", "future-return-up", "eth/usdt", "1H"
    )

    assert selected.model_id == "eth-champion"


def test_promotion_retires_only_the_matching_market_champion(repos):
    btc = _model("btc-champion", "champion", "BTC/USDT", "1h")
    eth = _model("eth-champion", "champion", "ETH/USDT", "1h")
    candidate = _model("btc-candidate", "candidate", "BTC/USDT", "1h")
    repos.session.add_all([btc, eth, candidate])
    repos.session.commit()

    repos.model_registry.promote_candidate("btc-candidate", "reviewer", "approved")

    assert repos.model_registry.get("btc-champion").status == "retired"
    assert repos.model_registry.get("btc-candidate").status == "champion"
    assert repos.model_registry.get("eth-champion").status == "champion"
