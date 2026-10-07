"""Editable retraining recipes, kept separate from completed training evidence."""

import json
import re

from app.factories.repository_factory import RepositoryFactory
from app.services.model_training_service import ModelTrainingService


class ModelTrainingSettingsService:
    def __init__(self, repository_factory=RepositoryFactory):
        self.repository_factory = repository_factory

    @staticmethod
    def _settings(model):
        try:
            metadata = json.loads(model.metadata_json or "{}")
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        saved = metadata.get("retraining_settings")
        if isinstance(saved, dict):
            return saved, []
        original = metadata.get("training_request")
        if isinstance(original, dict):
            return {"training": original, "interval_minutes": 60}, ["Check interval defaults to 60 minutes; it was not recorded with the trained model."]
        # Older models recorded the learner parameters and label, but not the
        # requested candle count or retention preference. Mark those defaults.
        training = {"feature_set_id": model.feature_set_id}
        context = metadata.get("market_context", {})
        if isinstance(context, dict):
            training.update({key: context[key] for key in ("symbol", "timeframe", "data_source") if key in context})
        config = metadata.get("training_config", {})
        if isinstance(config, dict):
            training.update({key: config[key] for key in ("n_estimators", "max_depth", "learning_rate", "probability_threshold") if key in config})
        label = re.fullmatch(r"future_return_up-n(\d+)-t([\d.eE+-]+)", model.label_definition_id or "")
        if label:
            training.update(horizon_candles=int(label[1]), up_return_threshold=float(label[2]))
        training = ModelTrainingService().validate_request(training)
        return {"training": training, "interval_minutes": 60}, ["Older model: missing settings use defaults. Verify candle count, replacement preference, source and check interval before saving."]

    def get(self, model_id):
        repos = self.repository_factory()
        try:
            model = repos.model_registry.get(model_id)
            if model is None:
                raise LookupError("model not found")
            settings, notes = self._settings(model)
            return {"model_id": model_id, **settings, "notes": notes}
        finally:
            repos.close()

    def save(self, model_id, request):
        interval = request.get("interval_minutes", 60)
        if isinstance(interval, bool) or not isinstance(interval, int) or not 5 <= interval <= 1440:
            raise ValueError("interval_minutes must be an integer between 5 and 1440")
        training = request.get("training")
        if not isinstance(training, dict):
            raise ValueError("training must be an object")
        settings = {"interval_minutes": interval, "training": ModelTrainingService().validate_request(training)}
        repos = self.repository_factory()
        try:
            repos.model_registry.save_training_settings(model_id, settings)
            return {"model_id": model_id, **settings, "notes": []}
        finally:
            repos.close()
