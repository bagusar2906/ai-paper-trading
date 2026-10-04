"""Manual, candidate-only training orchestration for the paper-trading UI."""

import logging
from pathlib import Path

from app.config import TradingConfig
from app.factories.provider_factory import create_provider
from app.factories.repository_factory import RepositoryFactory
from app.features.dataset import build_training_dataset
from app.labels.future_return import FutureReturnLabel
from app.ml.training import CandidateTrainer, CandidateTrainingConfig
from app.ml.validation import WalkForwardConfig

logger = logging.getLogger(__name__)

class ModelTrainingService:
    """Train and register an XGBoost candidate; never promote or execute it."""

    MIN_HISTORY_BARS = 250
    MAX_HISTORY_BARS = 5_000
    SUPPORTED_TIMEFRAMES = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}

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

    def train_candidate(self, request: dict) -> dict:
        symbol = self._string(request, "symbol", TradingConfig.SYMBOL)
        timeframe = self._string(request, "timeframe", TradingConfig.TIMEFRAME).upper()
        if timeframe not in self.SUPPORTED_TIMEFRAMES:
            raise ValueError(f"unsupported timeframe: {timeframe}")

        bars = self._integer(
            request, "bars", 1_000, self.MIN_HISTORY_BARS, self.MAX_HISTORY_BARS
        )
        horizon = self._integer(request, "horizon_candles", 12, 1, 100)
        threshold = self._number(request, "up_return_threshold", 0.003, 0.00001, 1)

        logger.info(
            "Starting candidate training symbol=%s timeframe=%s bars=%s horizon=%s threshold=%s",
            symbol, timeframe, bars, horizon, threshold,
        )

        provider = self.provider_factory()
        try:
            candles = provider.get_history(symbol, timeframe, bars)
        finally:
            provider.disconnect()

        definition = FutureReturnLabel(
            horizon_candles=horizon,
            up_return_threshold=threshold,
        )
        dataset = build_training_dataset(candles, definition)
        config = CandidateTrainingConfig(
            walk_forward=self._walk_forward_config(len(dataset.frame), horizon)
        )
        result = self.trainer_factory(self.artifact_directory).train(
            dataset, definition.name, config
        )

        repos = self.repository_factory()
        try:
            registered = repos.model_registry.record_candidate(result)
            # SQLAlchemy expires attributes after commit. Capture these while
            # the session remains open so the response does not access a
            # detached model instance after repos.close().
            model_id = registered.model_id
            status = registered.status
        finally:
            repos.close()

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
        }

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
