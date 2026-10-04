import pandas as pd

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
