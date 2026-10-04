import json
from types import SimpleNamespace

import pandas as pd
import pytest

from app.backtest.backtest_service import BacktestService
from app.labels.future_return import FutureReturnLabel
from app.ml.inference import ChampionUnavailable, RegisteredModelPredictor


def _model(model_id, status, metadata_json="{}"):
    return SimpleNamespace(
        model_id=model_id,
        status=status,
        feature_set_id="core-v1",
        label_definition_id=FutureReturnLabel(12, 0.003).definition_id,
        metadata_json=metadata_json,
    )


def test_candidate_comparison_uses_only_held_out_window():
    index = pd.date_range("2026-01-01", periods=8, freq="5min", tz="UTC")
    history = pd.DataFrame({"Close": range(8)}, index=index)

    selected = BacktestService._out_of_sample_history(history, index[5])

    assert list(selected.index) == list(index[5:])
    assert selected.index.min() >= index[5]


def test_candidate_comparison_rejects_missing_provenance(monkeypatch):
    candidate = _model("candidate-xgb-test", "candidate")
    champion = _model("champion-xgb-test", "champion")

    class Registry:
        def get(self, model_id):
            return candidate

        def get_champion(self, feature_set_id, label_definition_id):
            return champion

    repos = SimpleNamespace(model_registry=Registry(), close=lambda: None)
    monkeypatch.setattr("app.backtest.backtest_service.RepositoryFactory", lambda: repos)

    with pytest.raises(ValueError, match="retrain"):
        BacktestService()._comparison_models(
            "candidate-xgb-test", "XAUUSD", "M5", {}
        )


def test_candidate_comparison_requires_matching_market_context(monkeypatch):
    metadata = json.dumps({
        "market_context": {"symbol": "EURUSD", "timeframe": "M5"},
        "evaluation_window": {"start_time": "2026-01-01T01:00:00+00:00"},
    })
    candidate = _model("candidate-xgb-test", "candidate", metadata)
    champion = _model("champion-xgb-test", "champion")

    class Registry:
        def get(self, model_id):
            return candidate

        def get_champion(self, feature_set_id, label_definition_id):
            return champion

    repos = SimpleNamespace(model_registry=Registry(), close=lambda: None)
    monkeypatch.setattr("app.backtest.backtest_service.RepositoryFactory", lambda: repos)

    with pytest.raises(ValueError, match="different symbol"):
        BacktestService()._comparison_models(
            "candidate-xgb-test", "XAUUSD", "M5", {}
        )


def test_registered_predictor_rejects_wrong_status_before_artifact_access(monkeypatch):
    registered = _model("candidate-xgb-test", "candidate")
    repos = SimpleNamespace(
        model_registry=SimpleNamespace(get=lambda model_id: registered),
        close=lambda: None,
    )
    monkeypatch.setattr("app.ml.inference.RepositoryFactory", lambda: repos)

    with pytest.raises(ChampionUnavailable, match="not permitted"):
        RegisteredModelPredictor("candidate-xgb-test", {"champion"}).predict(
            pd.DataFrame([{}]), "core-v1", FutureReturnLabel(12, 0.003).definition_id
        )
