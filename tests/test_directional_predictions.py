import json
import pickle
from hashlib import sha256
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier

from app.backtest.backtest_service import BacktestService
from app.enums.signal_action import SignalAction
from app.features.dataset import build_training_dataset
from app.labels.future_return import FutureReturnLabel, add_future_return_label
from app.ml.inference import Prediction, _predict_registered
from app.ml.probabilities import positive_probability
from app.ml.training import CandidateTrainer, CandidateTrainingConfig
from app.ml.validation import WalkForwardConfig, generate_walk_forward_folds
from app.strategy.ai_assisted_xgb import AIAssistedXGBStrategy
from tests.test_ml_candidate_training import _candles


def test_labels_separate_falls_from_small_rises_and_flat_prices():
    candles = pd.DataFrame({"Close": [100, 102, 102.2, 100, 100]},
                           index=pd.date_range("2026-01-01", periods=5, freq="5min", tz="UTC"))
    label = FutureReturnLabel(1, .005)
    labeled = add_future_return_label(candles, label)
    assert labeled[label.name].iloc[:4].tolist() == [1, 0, 0, 0]
    assert labeled["future_return_down"].iloc[:4].tolist() == [0, 0, 1, 0]
    assert labeled["future_return_neutral"].iloc[:4].tolist() == [0, 1, 0, 1]
    assert labeled[[label.name, "future_return_down", "future_return_neutral"]].iloc[-1].isna().all()


@pytest.mark.parametrize("up,down,neutral,action", [
    (.12, .10, .78, SignalAction.HOLD),
    (.12, .78, .10, SignalAction.SELL),
    (.78, .12, .10, SignalAction.BUY),
    (.12, None, None, SignalAction.HOLD),
    (.12, None, .88, SignalAction.HOLD),
    (.45, .50, .05, SignalAction.HOLD),
    (.12, .90, .10, SignalAction.HOLD),
    (.12, float("nan"), .10, SignalAction.HOLD),
])
def test_sell_requires_valid_learned_downside_probability(up, down, neutral, action):
    predictor = SimpleNamespace(predict=lambda *args, **kwargs: Prediction("model", up, down, neutral))
    strategy = AIAssistedXGBStrategy({"feature_set_id": "raw-ohlcv-v1"}, predictor=predictor)
    signal = strategy.generate_signal("XAUUSD", _candles(20))
    assert signal.action == action
    if action == SignalAction.SELL:
        assert signal.confidence == down
        snapshot = BacktestService._decision_snapshot(signal)
        assert snapshot["probability"] == up
        assert snapshot["probability_down"] == down
    if down is None and neutral is None:
        assert "legacy UP-only" in signal.reason


def test_existing_short_cutoff_maps_to_a_required_fall_probability():
    strategy = AIAssistedXGBStrategy({"short_probability_threshold": .25})
    assert strategy.down_probability_threshold == .75
    assert AIAssistedXGBStrategy({"down_probability_threshold": .8}).down_probability_threshold == .8


@pytest.mark.parametrize("down_label", [0, 1])
def test_single_class_downside_history_does_not_invent_the_other_class(tmp_path, down_label):
    features = pd.DataFrame({"close_lag_0": range(8)})
    up = pd.Series([0, 1] * 4)
    down = pd.Series([down_label if item == 0 else 0 for item in up])
    config = CandidateTrainingConfig(WalkForwardConfig(4, 2, 2, 1, 0), n_estimators=2)
    model, calibrator, _ = CandidateTrainer(tmp_path)._fit_downside(features, up, down, config)
    assert positive_probability(model, calibrator, features).tolist() == [float(down_label)] * 8


@pytest.mark.parametrize("directional", [True, False])
def test_checked_artifact_distinguishes_downside_evidence_from_legacy_up_only(tmp_path, directional):
    features = pd.DataFrame({"close_lag_0": range(10)})
    up_model = DummyClassifier(strategy="prior").fit(features, [1] + [0] * 9)
    bundle = {"model": up_model, "calibrator": None}
    if directional:
        bundle["down_model"] = DummyClassifier(strategy="prior").fit(features, [0] + [1] * 9)
    artifact = tmp_path / "model.pkl"
    artifact.write_bytes(pickle.dumps(bundle))
    registered = SimpleNamespace(model_id="test", feature_set_id="raw-ohlcv-v1",
                                 label_definition_id="label", artifact_path=str(artifact),
                                 artifact_sha256=sha256(artifact.read_bytes()).hexdigest())
    prediction = _predict_registered(registered, features.iloc[-1:], "raw-ohlcv-v1", "label")
    assert prediction.probability_up == pytest.approx(.1)
    if directional:
        assert prediction.probability_down == pytest.approx(.81)
        assert prediction.probability_neutral == pytest.approx(.09)
    else:
        assert prediction.probability_down is prediction.probability_neutral is None


def test_directional_training_keeps_future_labels_out_of_inputs_and_validation_out_of_fitting(tmp_path, monkeypatch):
    label = FutureReturnLabel(3, .001)
    dataset = build_training_dataset(_candles(240), label, "raw-ohlcv-v1")
    config = CandidateTrainingConfig(WalkForwardConfig(80, 25, 25, 3, 1), n_estimators=3)
    trainer = CandidateTrainer(tmp_path)
    seen = []
    original = trainer._fit_downside

    def fit(features, up, down, settings):
        assert tuple(features.columns) == dataset.snapshot.feature_columns
        seen.append(features.index.copy())
        return original(features, up, down, settings)

    monkeypatch.setattr(trainer, "_fit_downside", fit)
    trained = trainer.train(dataset, label.name, config)
    folds = generate_walk_forward_folds(len(dataset.frame), config.walk_forward)
    for indices, fold in zip(seen, [*folds, folds[-1]]):
        assert indices.equals(dataset.frame.iloc[fold.train_start:fold.train_end].index)
        assert indices.max() < dataset.frame.index[fold.validation_start]
    assert len(seen) == len(folds) + 1
    baseline = trained.metadata["prediction_baseline"]
    assert baseline["positive_rate"] + baseline["down_rate"] + baseline["neutral_rate"] == pytest.approx(1)
    assert trained.metadata["prediction_contract"]["outcomes"] == ["up", "down", "neutral"]

    # Training-version changes prevent an UP-only fingerprint being reused.
    from dataclasses import asdict
    old_settings = {"training_metadata_version": 2, "feature_set_id": dataset.snapshot.feature_set_id,
                    "label_definition_id": dataset.snapshot.label_definition_id,
                    "training_config": asdict(config), "market_context": {}}
    old_hash = sha256(json.dumps(old_settings, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert trained.metadata["training_identity"]["settings_sha256"] != old_hash
