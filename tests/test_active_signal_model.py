from types import SimpleNamespace

from app.api.models import _active_signal_model


def test_active_signal_model_exposes_matching_champion(monkeypatch):
    monkeypatch.setattr("app.api.models.TradingConfig.SYMBOL", "BTC/USDT")
    monkeypatch.setattr("app.api.models.TradingConfig.TIMEFRAME", "1h")
    champion = SimpleNamespace(model_id="btc-champion")
    registry = SimpleNamespace(get_champion=lambda *args: champion)
    strategy = SimpleNamespace(
        id=5, name="BTC AI", strategy_type="AI_ASSISTED_XGB",
        config={"horizon_candles": 12, "up_return_threshold": 0.003},
    )
    repos = SimpleNamespace(
        strategies=SimpleNamespace(get_active=lambda: strategy),
        model_registry=registry,
    )

    result = _active_signal_model(repos)

    assert result["signal_ready"] is True
    assert result["champion_model_id"] == "btc-champion"
    assert result["symbol"] == "BTC/USDT"
    assert result["downside_ready"] is False
    assert "SELL is disabled" in result["reason"]


def test_active_directional_champion_supports_sell():
    champion = SimpleNamespace(model_id="directional", metadata_json='{"prediction_contract":{"outcomes":["up","down","neutral"]}}')
    repos = SimpleNamespace(
        strategies=SimpleNamespace(get_active=lambda: SimpleNamespace(id=5, name="AI", strategy_type="AI_ASSISTED_XGB", config={})),
        model_registry=SimpleNamespace(get_champion=lambda *args: champion),
    )
    result = _active_signal_model(repos)
    assert result["signal_ready"] is True
    assert result["downside_ready"] is True
    assert "reason" not in result


def test_active_signal_model_explains_when_matching_champion_is_missing(monkeypatch):
    monkeypatch.setattr("app.api.models.TradingConfig.SYMBOL", "BTC/USDT")
    strategy = SimpleNamespace(
        id=5, name="BTC AI", strategy_type="AI_ASSISTED_XGB", config={},
    )
    repos = SimpleNamespace(
        strategies=SimpleNamespace(get_active=lambda: strategy),
        model_registry=SimpleNamespace(get_champion=lambda *args: None),
    )

    result = _active_signal_model(repos)

    assert result["signal_ready"] is False
    assert "No champion matches" in result["reason"]
