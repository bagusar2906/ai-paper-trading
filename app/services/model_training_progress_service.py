"""Read-only validation history for a selected model and its training family."""

import json
import math
from datetime import datetime, timezone

from app.database.models import TrainingRunEntity
from app.factories.repository_factory import RepositoryFactory


METRIC_KEYS = ("precision", "recall", "roc_auc", "brier_score", "log_loss")


def _object(value):
    try:
        result = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    return result if isinstance(result, dict) else {}


def _metrics(value):
    value = value if isinstance(value, dict) else {}
    result = {}
    for key in METRIC_KEYS:
        number = value.get(key)
        valid = type(number) in (int, float) and math.isfinite(number) and number >= 0
        result[key] = number if valid and (key == "log_loss" or number <= 1) else None
    return result


def _scores(scores):
    return {"up": _metrics(scores), "down": _metrics(scores.get("downside"))}


def _signature(metadata):
    market = metadata.get("market_context")
    if not isinstance(market, dict) or not all(market.get(key) for key in ("symbol", "timeframe", "data_source")):
        return None
    contract = metadata.get("prediction_contract") or {"outcomes": ["up"]}
    family = metadata.get("candidate_family")
    if isinstance(family, dict) and isinstance(family.get("key"), str) and family["key"]:
        recipe = {"family": family}
    else:
        recipe = metadata.get("training_request")
        if isinstance(recipe, dict):
            recipe = {key: value for key, value in recipe.items() if key != "replace_previous_candidate"}
        else:
            recipe = metadata.get("training_config")
        if not isinstance(recipe, dict) or not recipe:
            return None
    return {"market": market, "contract": contract, "recipe": recipe}


def _time(metadata, fallback):
    try:
        value = datetime.fromisoformat(str(metadata.get("created_at", "")).replace("Z", "+00:00"))
    except ValueError:
        value = fallback
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


class ModelTrainingProgressService:
    MAX_RUNS = 200

    def __init__(self, repository_factory=RepositoryFactory):
        self.repository_factory = repository_factory

    def get(self, model_id):
        repos = self.repository_factory()
        try:
            model = repos.model_registry.get(model_id)
            if model is None:
                raise LookupError("model not found")
            metadata = _object(model.metadata_json)
            signature = _signature(metadata)
            query = repos.session.query(TrainingRunEntity).filter_by(
                feature_set_id=model.feature_set_id,
                label_definition_id=model.label_definition_id,
                status="completed",
            ).order_by(TrainingRunEntity.created_at.desc(), TrainingRunEntity.training_run_id.desc())
            runs, limited = [], False
            for run in query.yield_per(100):
                details = _object(run.metadata_json)
                selected = run.training_run_id == model.training_run_id
                if not selected and (signature is None or _signature(details) != signature):
                    continue
                if len(runs) >= self.MAX_RUNS:
                    limited = True
                    break
                runs.append(self._point(run, details, selected))
            if not any(point["selected"] for point in runs):
                if len(runs) >= self.MAX_RUNS:
                    runs.pop()
                runs.append(self._point(model, metadata, True))
            runs.sort(key=lambda point: (point["created_at"] or "", point["training_run_id"]))
            raw_folds = metadata.get("folds", [])
            raw_folds = raw_folds if isinstance(raw_folds, list) else []
            folds = []
            for number, fold in enumerate(raw_folds[:200], start=1):
                if not isinstance(fold, dict):
                    continue
                folds.append({"label": f"Period {number}", "selected": False,
                              "validation_start": self._text(fold.get("validation_start")),
                              "validation_end": self._text(fold.get("validation_end")),
                              "metrics": {"up": _metrics(fold.get("metrics")),
                                          "down": _metrics(fold.get("down_metrics"))}})
            return {"model_id": model_id, "status": model.status,
                    "runs": runs, "folds": folds, "limited": limited,
                    "matching_history_available": signature is not None,
                    "notes": [
                        "Scores are from completed training runs, not a live percentage-complete indicator.",
                        "Related runs use the same recorded market, training recipe and prediction type. Evaluation periods may differ; compare on the same unseen candles before judging improvement.",
                        "Validation periods belong to the selected training run and can overlap. Fluctuations do not mean the model learns continuously.",
                    ]}
        finally:
            repos.close()

    @staticmethod
    def _text(value):
        return value if isinstance(value, str) else None

    @staticmethod
    def _point(record, metadata, selected):
        return {"training_run_id": record.training_run_id,
                "model_id": metadata.get("model_id") if isinstance(metadata.get("model_id"), str) else getattr(record, "model_id", None),
                "created_at": _time(metadata, record.created_at), "selected": selected,
                "metrics": _scores(_object(record.metrics_json))}
