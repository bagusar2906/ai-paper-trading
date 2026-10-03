"""Candidate-only XGBoost training with chronological walk-forward scoring."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import pickle
import platform
import sys
from uuid import uuid4

import numpy as np
from sklearn.linear_model import LogisticRegression
import sklearn
import xgboost
from xgboost import XGBClassifier

from app.features.dataset import TrainingDataset
from app.ml.metrics import classification_metrics, reliability_bins
from app.ml.validation import WalkForwardConfig, generate_walk_forward_folds


@dataclass(frozen=True)
class CandidateTrainingConfig:
    walk_forward: WalkForwardConfig
    random_seed: int = 42
    probability_threshold: float = 0.5
    calibration_fraction: float = 0.2
    n_estimators: int = 100
    max_depth: int = 3
    learning_rate: float = 0.05

    def __post_init__(self):
        if not 0 < self.probability_threshold < 1:
            raise ValueError("probability_threshold must be between zero and one")
        if not 0 < self.calibration_fraction < 0.5:
            raise ValueError("calibration_fraction must be between zero and 0.5")


@dataclass(frozen=True)
class CandidateTrainingResult:
    training_run_id: str
    model_id: str
    status: str
    artifact_path: Path
    artifact_sha256: str
    metrics: dict
    metadata: dict


class CandidateTrainer:
    """Produces offline candidates only; promotion and inference are out of scope."""

    def __init__(self, artifact_directory: Path | str):
        self.artifact_directory = Path(artifact_directory)

    def train(self, dataset: TrainingDataset, label_column: str, config: CandidateTrainingConfig) -> CandidateTrainingResult:
        if label_column not in dataset.frame:
            raise ValueError(f"dataset is missing label column: {label_column}")
        frame = dataset.frame.sort_index()
        features = list(dataset.snapshot.feature_columns)
        if list(frame.loc[:, features].columns) != features:
            raise ValueError("dataset feature columns do not match the registered feature contract")
        target = frame[label_column].astype(int)
        folds = generate_walk_forward_folds(len(frame), config.walk_forward)

        all_y, all_probabilities, fold_reports = [], [], []
        for number, fold in enumerate(folds, start=1):
            x_train = frame.iloc[fold.train_start:fold.train_end][features]
            y_train = target.iloc[fold.train_start:fold.train_end]
            x_validation = frame.iloc[fold.validation_start:fold.validation_end][features]
            y_validation = target.iloc[fold.validation_start:fold.validation_end]
            model, calibrator, calibration_method = self._fit_with_chronological_calibration(
                x_train, y_train, config
            )
            probabilities = self._predict_probability(model, calibrator, x_validation)
            all_y.extend(y_validation.tolist())
            all_probabilities.extend(probabilities.tolist())
            fold_reports.append({
                "fold": number,
                "train_start": str(x_train.index.min()),
                "train_end": str(x_train.index.max()),
                "validation_start": str(x_validation.index.min()),
                "validation_end": str(x_validation.index.max()),
                "rows_train": len(x_train),
                "rows_validation": len(x_validation),
                "calibration_method": calibration_method,
                "metrics": classification_metrics(y_validation, probabilities, config.probability_threshold),
            })

        # The persisted candidate is fit using the last chronological split:
        # training/candidate calibration remain separated, and no validation
        # rows from that fold are used to fit it.
        final_fold = folds[-1]
        final_x = frame.iloc[final_fold.train_start:final_fold.train_end][features]
        final_y = target.iloc[final_fold.train_start:final_fold.train_end]
        model, calibrator, calibration_method = self._fit_with_chronological_calibration(
            final_x, final_y, config
        )

        training_run_id = f"train-{uuid4().hex[:12]}"
        model_id = f"candidate-xgb-{uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()
        metrics = classification_metrics(all_y, all_probabilities, config.probability_threshold)
        metrics["reliability_bins"] = reliability_bins(all_y, all_probabilities)
        metadata = {
            "model_id": model_id,
            "training_run_id": training_run_id,
            "status": "candidate",
            "created_at": created_at,
            "feature_snapshot": {
                "feature_set_id": dataset.snapshot.feature_set_id,
                "feature_set_version": dataset.snapshot.feature_set_version,
                "feature_columns": list(dataset.snapshot.feature_columns),
                "label_definition_id": dataset.snapshot.label_definition_id,
                "start_time": str(dataset.snapshot.start_time),
                "end_time": str(dataset.snapshot.end_time),
                "row_count": dataset.snapshot.row_count,
            },
            "training_config": asdict(config),
            "folds": fold_reports,
            "calibration_method": calibration_method,
            "package_versions": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "xgboost": xgboost.__version__,
                "scikit_learn": sklearn.__version__,
            },
        }
        self.artifact_directory.mkdir(parents=True, exist_ok=True)
        artifact_path = self.artifact_directory / f"{model_id}.pkl"
        with artifact_path.open("wb") as stream:
            pickle.dump({"model": model, "calibrator": calibrator, "metadata": metadata}, stream)
        checksum = sha256(artifact_path.read_bytes()).hexdigest()
        metadata_path = self.artifact_directory / f"{model_id}.json"
        metadata_path.write_text(json.dumps({**metadata, "metrics": metrics, "artifact_sha256": checksum}, indent=2), encoding="utf-8")
        return CandidateTrainingResult(training_run_id, model_id, "candidate", artifact_path, checksum, metrics, metadata)

    @staticmethod
    def _model(config: CandidateTrainingConfig) -> XGBClassifier:
        return XGBClassifier(
            n_estimators=config.n_estimators,
            max_depth=config.max_depth,
            learning_rate=config.learning_rate,
            random_state=config.random_seed,
            eval_metric="logloss",
            n_jobs=1,
        )

    def _fit_with_chronological_calibration(self, x_train, y_train, config):
        calibration_size = max(1, int(len(x_train) * config.calibration_fraction))
        model_end = len(x_train) - calibration_size
        if model_end < 2 or y_train.iloc[:model_end].nunique() < 2:
            if y_train.nunique() < 2:
                raise ValueError("each training fold must contain both label classes")
            model = self._model(config).fit(x_train, y_train)
            return model, None, "none_insufficient_calibration_history"
        model = self._model(config).fit(x_train.iloc[:model_end], y_train.iloc[:model_end])
        calibration_x = x_train.iloc[model_end:]
        calibration_y = y_train.iloc[model_end:]
        if calibration_y.nunique() < 2:
            return model, None, "none_single_class_calibration_history"
        calibration_probability = model.predict_proba(calibration_x)[:, 1]
        calibrator = LogisticRegression(random_state=config.random_seed).fit(
            calibration_probability.reshape(-1, 1), calibration_y
        )
        return model, calibrator, "platt_logistic_regression"

    @staticmethod
    def _predict_probability(model, calibrator, features):
        probability = model.predict_proba(features)[:, 1]
        if calibrator is not None:
            probability = calibrator.predict_proba(probability.reshape(-1, 1))[:, 1]
        return np.clip(probability, 0.0, 1.0)
