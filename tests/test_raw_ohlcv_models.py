import json
from types import SimpleNamespace

import pandas as pd
import pytest

from app.api.models import _active_signal_model
from app.backtest.backtest_service import BacktestService
from app.features.raw_ohlcv_v1 import RAW_OHLCV_FEATURE_COLUMNS, build_raw_ohlcv_features
from app.features.dataset import build_training_dataset
from app.labels.future_return import FutureReturnLabel
from app.ml.inference import Prediction, RegisteredModelPredictor
from app.ml.training import CandidateTrainer, CandidateTrainingConfig
from app.ml.validation import WalkForwardConfig
from app.strategy.ai_assisted_xgb import AIAssistedXGBStrategy
from app.enums.signal_action import SignalAction
from tests.test_ml_candidate_training import _candles


def test_raw_features_have_only_current_and_lagged_ohlcv_and_no_future_leakage():
    candles = _candles(50)
    features = build_raw_ohlcv_features(candles)
    assert tuple(features.columns) == RAW_OHLCV_FEATURE_COLUMNS
    assert len(features.columns) == 60
    assert len(features) == 39
    assert features.iloc[0]["close_lag_11"] == candles.iloc[0]["Close"]
    modified = candles.copy()
    modified.iloc[30:, :4] += 1000
    pd.testing.assert_frame_equal(features.loc[:candles.index[29]], build_raw_ohlcv_features(modified).loc[:candles.index[29]])
    assert not any("rsi" in column or "adx" in column or "atr" in column or "ema" in column for column in features.columns)


@pytest.mark.parametrize("probability,action", [(.8, SignalAction.BUY), (.2, SignalAction.SELL), (.5, SignalAction.HOLD)])
def test_raw_strategy_uses_only_probability_with_fixed_percentage_risk(monkeypatch, probability, action):
    monkeypatch.setattr("app.strategy.ai_assisted_xgb.build_core_v1_features", lambda _: pytest.fail("raw mode must never build technical indicators"))
    predictor = SimpleNamespace(predict=lambda features, feature_set_id, *args, **kwargs: Prediction("raw-champion", probability) if feature_set_id == "raw-ohlcv-v1" else pytest.fail("wrong contract"))
    strategy = AIAssistedXGBStrategy({"feature_set_id": "raw-ohlcv-v1", "model_stop_loss_percent": 1}, predictor=predictor)
    signal = strategy.generate_signal("XAUUSD", _candles(20))
    assert strategy.minimum_bars == 12
    assert signal.action == action
    assert signal.ema is signal.rsi is signal.adx is None
    assert signal.ai_lab_context["regime"] == "model_probability"
    if action == SignalAction.BUY:
        assert signal.stop_loss == pytest.approx(signal.price * .99)
    if action == SignalAction.SELL:
        assert signal.stop_loss == pytest.approx(signal.price * 1.01)


def test_raw_model_can_train_register_predict_and_replay(tmp_path, repos, monkeypatch):
    candles = _candles(240)
    label = FutureReturnLabel(3, .0001)
    dataset = build_training_dataset(candles, label, "raw-ohlcv-v1")
    assert dataset.snapshot.feature_set_id == "raw-ohlcv-v1"
    config = CandidateTrainingConfig(walk_forward=WalkForwardConfig(80, 25, 25, 3, 1), n_estimators=8)
    trained = CandidateTrainer(tmp_path, {"symbol": "XAUUSD", "timeframe": "M5"}).train(dataset, label.name, config)
    registered = repos.model_registry.record_candidate(trained)
    registered_id = registered.model_id
    monkeypatch.setattr("app.ml.inference.RepositoryFactory", lambda: repos)
    predictor = RegisteredModelPredictor(registered_id, {"candidate"})
    prediction = predictor.predict(build_raw_ohlcv_features(candles).iloc[-1:], "raw-ohlcv-v1", label.definition_id)
    assert 0 <= prediction.probability_up <= 1
    strategy = AIAssistedXGBStrategy({"feature_set_id": "raw-ohlcv-v1", "horizon_candles": 3, "up_return_threshold": .0001}, predictor=predictor)
    request = SimpleNamespace(symbol="XAUUSD", timeframe="M5", bars=30, initial_balance=10000)
    report = BacktestService()._run_strategy(request, candles.iloc[-30:], strategy, None, collect_decisions=True)
    assert len(report.decision_trace) == 18
    assert all(row["model_id"] == registered_id for row in report.decision_trace)
    assert all(row["gates"]["technical_filters_enabled"] is False for row in report.decision_trace)
    assert "rsi_14" not in trained.metadata["feature_baseline"]


def test_active_signal_and_comparison_look_up_raw_champion(monkeypatch):
    config = {"feature_set_id": "raw-ohlcv-v1"}
    metadata = json.dumps({"market_context": {"symbol": "XAUUSD", "timeframe": "M5"}, "evaluation_window": {"start_time": "2026-01-01T00:00:00Z"}})
    candidate = SimpleNamespace(model_id="raw-a", status="candidate", feature_set_id="raw-ohlcv-v1", label_definition_id=FutureReturnLabel(12, .003).definition_id, metadata_json=metadata)
    champion = SimpleNamespace(model_id="raw-b", metadata_json=metadata)
    def lookup(feature_set, *args):
        assert feature_set == "raw-ohlcv-v1"
        return champion
    repos = SimpleNamespace(model_registry=SimpleNamespace(get=lambda _: candidate, get_champion=lookup), strategies=SimpleNamespace(get_active=lambda: SimpleNamespace(id=2, name="Raw", strategy_type="AI_ASSISTED_XGB", config=config)), close=lambda: None)
    monkeypatch.setattr("app.backtest.backtest_service.RepositoryFactory", lambda: repos)
    assert BacktestService()._comparison_models("raw-a", "XAUUSD", "M5", config)[1] == champion
    assert _active_signal_model(repos)["feature_set_id"] == "raw-ohlcv-v1"


def test_invalid_raw_configuration_and_missing_history_do_not_trade():
    with pytest.raises(ValueError, match="filters"):
        AIAssistedXGBStrategy({"feature_set_id": "raw-ohlcv-v1", "use_technical_filters": True})
    with pytest.raises(ValueError, match="boolean"):
        AIAssistedXGBStrategy({"use_technical_filters": "false"})
    with pytest.raises(ValueError, match="probability thresholds"):
        AIAssistedXGBStrategy({"long_probability_threshold": .3, "short_probability_threshold": .7})
    signal = AIAssistedXGBStrategy({"feature_set_id": "raw-ohlcv-v1"}).generate_signal("XAUUSD", _candles(5))
    assert signal.action == SignalAction.HOLD
