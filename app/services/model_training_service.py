"""Manual, candidate-only training orchestration for the paper-trading UI."""

import logging
from hashlib import sha256
import json
from pathlib import Path
from threading import Lock

from app.config import TradingConfig
from app.factories.provider_factory import create_provider
from app.factories.repository_factory import RepositoryFactory
from app.features.dataset import build_training_dataset
from app.labels.future_return import FutureReturnLabel
from app.ml.training import CandidateTrainer, CandidateTrainingConfig
from app.ml.validation import WalkForwardConfig
from app.services.training_data_sync_service import TrainingDataSyncService
from app.services.model_lab_data_source_service import ModelLabDataSourceService

logger = logging.getLogger(__name__)

class ModelTrainingService:
    """Train and register an XGBoost candidate; never promote or execute it."""

    MIN_HISTORY_BARS = 250
    MAX_HISTORY_BARS = 5_000
    SUPPORTED_TIMEFRAMES = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}
    _training_lock = Lock()

    def __init__(
        self,
        provider_factory=create_provider,
        repository_factory=RepositoryFactory,
        trainer_factory=CandidateTrainer,
        artifact_directory: Path | str = "data/model_artifacts",
    ):
        self.provider_factory = provider_factory
        self.repository_factory = repository_factory
        self.trainer_factory = trainer_factory
        self.artifact_directory = Path(artifact_directory)

    def train_candidate(self, request: dict, *, backfill: bool = False) -> dict:
        if not self._training_lock.acquire(blocking=False):
            raise RuntimeError("Another model training run is already in progress. Try again after it finishes.")
        try:
            return self._train_candidate(request, backfill=backfill)
        finally:
            self._training_lock.release()

    def validate_request(self, request: dict) -> dict:
        replace_previous = request.get("replace_previous_candidate", True)
        if not isinstance(replace_previous, bool):
            raise ValueError("replace_previous_candidate must be a boolean")
        data_source = ModelLabDataSourceService.validate(request.get("data_source", "trading"))
        symbol = self._string(request, "symbol", TradingConfig.SYMBOL)
        timeframe = self._string(request, "timeframe", TradingConfig.TIMEFRAME).upper()
        if timeframe not in self.SUPPORTED_TIMEFRAMES:
            raise ValueError(f"unsupported timeframe: {timeframe}")

        bars = self._integer(
            request, "bars", 1_000, self.MIN_HISTORY_BARS, self.MAX_HISTORY_BARS
        )
        horizon = self._integer(request, "horizon_candles", 12, 1, 100)
        threshold = self._number(request, "up_return_threshold", 0.003, 0.00001, 1)
        n_estimators = self._integer(request, "n_estimators", 100, 25, 500)
        max_depth = self._integer(request, "max_depth", 3, 1, 8)
        learning_rate = self._number(request, "learning_rate", 0.05, 0.01, 0.30)
        probability_threshold = self._number(request, "probability_threshold", 0.50, 0.40, 0.70)
        feature_set_id = self._string(request, "feature_set_id", "core-v1")
        if feature_set_id not in {"core-v1", "raw-ohlcv-v1"}:
            raise ValueError(f"unsupported feature set: {feature_set_id}")
        return {
            "symbol": symbol, "timeframe": timeframe, "bars": bars,
            "horizon_candles": horizon, "up_return_threshold": threshold,
            "n_estimators": n_estimators, "max_depth": max_depth,
            "learning_rate": learning_rate, "probability_threshold": probability_threshold,
            "feature_set_id": feature_set_id,
            "data_source": data_source,
            "replace_previous_candidate": replace_previous,
        }

    def _train_candidate(self, request: dict, *, backfill: bool = False) -> dict:
        parameters = self.validate_request(request)
        symbol, timeframe, bars = (parameters[key] for key in ("symbol", "timeframe", "bars"))
        horizon, threshold = parameters["horizon_candles"], parameters["up_return_threshold"]
        n_estimators, max_depth = parameters["n_estimators"], parameters["max_depth"]
        learning_rate, probability_threshold = parameters["learning_rate"], parameters["probability_threshold"]
        feature_set_id = parameters["feature_set_id"]

        logger.info(
            "Starting candidate training symbol=%s timeframe=%s bars=%s horizon=%s threshold=%s",
            symbol, timeframe, bars, horizon, threshold,
        )

        provider = self.provider_factory() if parameters["data_source"] == "trading" else self.provider_factory(parameters["data_source"])
        data_sync = None
        try:
            if backfill:
                candles, data_sync = TrainingDataSyncService(self.repository_factory).synchronize(provider, symbol, timeframe, bars)
            else:
                candles = provider.get_history(symbol, timeframe, bars)
        finally:
            provider.disconnect()

        definition = FutureReturnLabel(
            horizon_candles=horizon,
            up_return_threshold=threshold,
        )
        dataset = build_training_dataset(candles, definition, feature_set_id)
        config = CandidateTrainingConfig(
            walk_forward=self._walk_forward_config(len(dataset.frame), horizon),
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            probability_threshold=probability_threshold,
        )
        market_context = {"symbol": symbol.upper(), "timeframe": timeframe}
        source = getattr(provider, "source_name", None)
        if source:
            market_context["data_source"] = source
        identity = CandidateTrainer.training_identity(dataset, config, market_context)
        family_settings = {key: value for key, value in parameters.items() if key != "replace_previous_candidate"}
        family_settings.update(symbol=symbol.upper(), data_source=source or parameters["data_source"])
        family = {"key": sha256(json.dumps(family_settings, sort_keys=True).encode()).hexdigest(),
                  "origin": "self_training" if backfill else "manual"}

        repos = self.repository_factory()
        try:
            existing = repos.model_registry.find_by_training_fingerprint(
                identity["fingerprint"]
            )
            if existing is not None:
                removed = repos.model_registry.replace_matching_candidates(existing.model_id, family) if parameters["replace_previous_candidate"] else []
                cleanup_warnings = self._remove_replaced_artifacts(removed)
                return {
                    "model_id": existing.model_id,
                    "status": "duplicate",
                    "data_sync": data_sync,
                    "replaced_model_ids": [item["model_id"] for item in removed],
                    "cleanup_warnings": cleanup_warnings,
                    "message": "An existing model was trained with the same market data and settings. No new candidate was created.",
                }
        finally:
            repos.close()

        trainer = self.trainer_factory(
            self.artifact_directory,
            market_context=market_context,
        )
        result = trainer.train(
            dataset, definition.name, config
        )
        if isinstance(getattr(result, "metadata", None), dict):
            result.metadata["candidate_family"] = family
        if parameters["replace_previous_candidate"]:
            artifact = Path(result.artifact_path)
            if not artifact.is_file() or sha256(artifact.read_bytes()).hexdigest() != result.artifact_sha256:
                self._remove_replaced_artifacts([{"model_id": result.model_id, "artifact_path": str(artifact)}])
                raise ValueError("New model artifact could not be verified; previous candidates were kept")

        repos = self.repository_factory()
        try:
            registered = repos.model_registry.record_candidate(result, replace_matching=True) if parameters["replace_previous_candidate"] else repos.model_registry.record_candidate(result)
            # SQLAlchemy expires attributes after commit. Capture these while
            # the session remains open so the response does not access a
            # detached model instance after repos.close().
            model_id = registered.model_id
            status = registered.status
            removed = getattr(registered, "_replaced_candidates", [])
        except Exception:
            if getattr(result, "artifact_path", None):
                self._remove_replaced_artifacts([{"model_id": result.model_id, "artifact_path": str(result.artifact_path)}])
            raise
        finally:
            repos.close()
        cleanup_warnings = self._remove_replaced_artifacts(removed)

        logger.info(
            "Candidate training completed model_id=%s training_run_id=%s rows=%s",
            model_id, result.training_run_id, dataset.snapshot.row_count,
        )

        return {
            "model_id": model_id,
            "training_run_id": result.training_run_id,
            "status": status,
            "symbol": symbol,
            "timeframe": timeframe,
            "history_bars": bars,
            "training_rows": dataset.snapshot.row_count,
            "feature_set_id": dataset.snapshot.feature_set_id,
            "label_definition_id": dataset.snapshot.label_definition_id,
            "metrics": result.metrics,
            "data_source": source,
            "data_sync": data_sync,
            "replaced_model_ids": [item["model_id"] for item in removed],
            "cleanup_warnings": cleanup_warnings,
        }

    def _remove_replaced_artifacts(self, removed):
        warnings = []
        root = self.artifact_directory.resolve()
        for item in removed:
            artifact = Path(item["artifact_path"])
            for target in (artifact, artifact.with_suffix(".json")):
                path = target.resolve()
                if root not in path.parents:
                    warnings.append(f"Artifact outside the managed folder was kept: {item['model_id']}")
                    continue
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Could not remove superseded candidate artifact: %s", path, exc_info=True)
                    warnings.append(f"Could not remove superseded artifact: {item['model_id']}")
        return warnings

    @staticmethod
    def _walk_forward_config(row_count: int, horizon: int) -> WalkForwardConfig:
        # Use expanding, chronological folds. The purge matches the future
        # label horizon, so training labels cannot overlap validation prices.
        initial_train_size = max(100, row_count // 2)
        validation_size = max(25, row_count // 7)
        return WalkForwardConfig(
            initial_train_size=initial_train_size,
            validation_size=validation_size,
            step_size=validation_size,
            purge_candles=horizon,
            embargo_candles=1,
        )

    @staticmethod
    def _string(request: dict, name: str, default: str) -> str:
        value = request.get(name, default)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _integer(request: dict, name: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(request.get(name, default))
        except (TypeError, ValueError) as error:
            raise ValueError(f"{name} must be an integer") from error
        if not minimum <= value <= maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}")
        return value

    @staticmethod
    def _number(request: dict, name: str, default: float, minimum: float, maximum: float) -> float:
        try:
            value = float(request.get(name, default))
        except (TypeError, ValueError) as error:
            raise ValueError(f"{name} must be a number") from error
        if not minimum <= value <= maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}")
        return value
