import numpy as np
import pandas as pd

from app.features.dataset import build_training_dataset
from app.labels import FutureReturnLabel
from app.ml.training import CandidateTrainingConfig, CandidateTrainer
from app.ml.validation import WalkForwardConfig, generate_walk_forward_folds


def _candles(count=240):
    index = pd.date_range("2026-01-01", periods=count, freq="5min", tz="UTC")
    # Oscillation deliberately creates both positive and negative future returns.
    close = 2000 + np.sin(np.arange(count) / 2) * 8 + np.arange(count) * 0.01
    open_ = close + np.cos(np.arange(count)) * 0.15
    return pd.DataFrame({
        "Open": open_,
        "High": np.maximum(open_, close) + 0.5,
        "Low": np.minimum(open_, close) - 0.5,
        "Close": close,
        "Volume": 100 + np.arange(count),
    }, index=index)


def test_walk_forward_splits_are_chronological_and_purged():
    config = WalkForwardConfig(
        initial_train_size=60,
        validation_size=20,
        step_size=20,
        purge_candles=3,
        embargo_candles=2,
    )
    folds = generate_walk_forward_folds(160, config)
    assert folds
    for fold in folds:
        assert fold.train_start == 0
        assert fold.train_end + config.purge_candles == fold.validation_start
        assert fold.train_end < fold.validation_start < fold.validation_end


def test_candidate_training_persists_an_auditable_candidate_artifact(tmp_path, repos):
    definition = FutureReturnLabel(horizon_candles=3, up_return_threshold=0.0001)
    dataset = build_training_dataset(_candles(), definition)
    config = CandidateTrainingConfig(
        walk_forward=WalkForwardConfig(
            initial_train_size=80,
            validation_size=25,
            step_size=25,
            purge_candles=definition.horizon_candles,
            embargo_candles=1,
        ),
        n_estimators=8,
        max_depth=2,
        learning_rate=0.2,
    )

    result = CandidateTrainer(tmp_path).train(dataset, definition.name, config)

    assert result.status == "candidate"
    assert result.training_run_id.startswith("train-")
    assert result.model_id.startswith("candidate-xgb-")
    assert result.artifact_path.is_file()
    assert len(result.artifact_sha256) == 64
    assert result.metadata["feature_snapshot"]["label_definition_id"] == definition.definition_id
    assert result.metadata["training_config"]["walk_forward"]["purge_candles"] == 3
    assert "brier_score" in result.metrics
    assert result.metrics["reliability_bins"]

    registered = repos.model_registry.record_candidate(result)
    assert registered.status == "candidate"
    assert repos.model_registry.get(result.model_id).artifact_sha256 == result.artifact_sha256
    champion = repos.model_registry.promote_candidate(result.model_id, "reviewer", "out-of-sample review")
    assert champion.status == "champion"
    champion.status = "retired"
    repos.session.commit()
    assert repos.model_registry.rollback(result.model_id, "reviewer", "rollback exercise").status == "champion"
