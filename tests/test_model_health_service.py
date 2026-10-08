import pandas as pd
import pytest

from app.services.model_health_service import ModelHealthService


def test_health_reports_healthy_when_recent_features_match_baseline():
    features = pd.DataFrame({"rsi_14": [50.0] * 60, "adx_14": [25.0] * 60})
    baseline = {"rsi_14": {"median": 50.0, "iqr": 5.0}, "adx_14": {"median": 25.0, "iqr": 4.0}}

    report = ModelHealthService().assess(baseline, features)

    assert report["status"] == "healthy"
    assert report["recommendation"] == "continue_monitoring"


def test_health_recommends_retraining_plan_when_many_features_drift():
    features = pd.DataFrame({"rsi_14": [90.0] * 60, "adx_14": [60.0] * 60})
    baseline = {"rsi_14": {"median": 50.0, "iqr": 5.0}, "adx_14": {"median": 25.0, "iqr": 4.0}}

    report = ModelHealthService().assess(baseline, features)

    assert report["status"] == "watch"
    assert report["recommendation"] == "review_market_regime"


@pytest.mark.parametrize("enabled", [True, False])
def test_health_uses_raw_inputs_for_a_raw_champion(monkeypatch, enabled):
    import json
    from types import SimpleNamespace
    from app.features.raw_ohlcv_v1 import build_raw_ohlcv_features
    from tests.test_ml_candidate_training import _candles
    candles = _candles(100)
    features = build_raw_ohlcv_features(candles).tail(50)
    baseline = {column: {"median": float(features[column].median()), "iqr": 10} for column in features.columns}
    champion = SimpleNamespace(model_id="raw-champion", status="champion", feature_set_id="raw-ohlcv-v1", metadata_json=json.dumps({"market_context": {"symbol": "XAUUSD", "timeframe": "M5"}, "feature_baseline": baseline}))
    stored = {"model_self_training_config": json.dumps({"enabled": enabled})}
    repos = SimpleNamespace(model_registry=SimpleNamespace(get_all=lambda: [champion]),
                            settings=SimpleNamespace(get=lambda key, default=None: stored.get(key, default)),
                            close=lambda: None)
    provider = SimpleNamespace(get_history=lambda *args: candles, disconnect=lambda: None)
    monkeypatch.setattr("app.services.model_health_service.build_core_v1_features", lambda _: (_ for _ in ()).throw(AssertionError("must not calculate indicators")))
    report = ModelHealthService(provider_factory=lambda: provider, repository_factory=lambda: repos).check()
    assert report["status"] == "healthy"
    assert "60 monitored features" in report["reasons"][0]
    assert report["automatic_retraining"] is enabled
    stored["model_self_training_config"] = json.dumps({"enabled": not enabled})
    assert ModelHealthService(provider_factory=lambda: provider, repository_factory=lambda: repos).check()["automatic_retraining"] is not enabled


@pytest.mark.parametrize("config, expected", [
    ('{"enabled": true}', True),
    ('{"enabled": false}', False),
    ('{"enabled": "false"}', False),
    ('{}', False),
    ('null', False),
    ('invalid-json', False),
])
def test_health_without_champion_reports_saved_self_training_setting(repos, monkeypatch, config, expected):
    monkeypatch.setattr(repos, "close", lambda: None)
    repos.settings.set("model_self_training_config", config)

    report = ModelHealthService(repository_factory=lambda: repos).check()

    assert report["recommendation"] == "no_champion"
    assert report["automatic_retraining"] is expected
