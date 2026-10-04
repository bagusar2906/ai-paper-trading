import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.factories.repository_factory import RepositoryFactory
from app.services.model_experiment_service import ModelExperimentService
from app.services.model_health_service import ModelHealthService
from app.services.model_review_guidance_service import ModelReviewGuidanceService
from app.services.model_improvement_service import ModelImprovementService
from app.services.model_training_service import ModelTrainingService

router = APIRouter(prefix="/models", tags=["Models"])
logger = logging.getLogger(__name__)


@router.post("/train")
def train_candidate(request: dict):
    """Train and register a paper-only candidate from completed candles."""
    try:
        return ModelTrainingService().train_candidate(request)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("Candidate training failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail="Candidate training failed unexpectedly. Check the server log.",
        ) from error


@router.get("")
def list_models():
    repos = RepositoryFactory()
    try:
        models = repos.model_registry.get_all()
        return [{
            "model_id": item.model_id,
            "status": item.status,
            "feature_set_id": item.feature_set_id,
            "label_definition_id": item.label_definition_id,
            "created_at": item.created_at,
            "metrics": _decode_metrics(item.metrics_json),
            # Context is non-secret provenance used only to prevent a
            # candidate comparison from silently using a different market.
            "market_context": _market_context(getattr(item, "metadata_json", None)),
            "feature_importance": _feature_importance(getattr(item, "metadata_json", None)),
        } for item in models]
    finally:
        repos.close()


def _decode_metrics(metrics_json: str) -> dict:
    """Keep legacy/corrupt registry metadata from breaking the dashboard."""
    try:
        metrics = json.loads(metrics_json)
    except (TypeError, json.JSONDecodeError):
        return {}
    return metrics if isinstance(metrics, dict) else {}


def _market_context(metadata_json: str | None) -> dict | None:
    try:
        metadata = json.loads(metadata_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return None
    context = metadata.get("market_context") if isinstance(metadata, dict) else None
    if not isinstance(context, dict):
        return None
    symbol, timeframe = context.get("symbol"), context.get("timeframe")
    if not isinstance(symbol, str) or not isinstance(timeframe, str):
        return None
    return {"symbol": symbol, "timeframe": timeframe}


def _feature_importance(metadata_json: str | None) -> list[dict]:
    """Expose only valid, bounded attribution values for dashboard review."""
    try:
        metadata = json.loads(metadata_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return []
    importance = metadata.get("feature_importance") if isinstance(metadata, dict) else None
    if not isinstance(importance, list):
        return []
    return [
        {"feature": item["feature"], "importance": item["importance"]}
        for item in importance[:5]
        if isinstance(item, dict)
        and isinstance(item.get("feature"), str)
        and isinstance(item.get("importance"), (int, float))
    ]


@router.get("/champion")
def champion(feature_set_id: str, label_definition_id: str):
    repos = RepositoryFactory()
    try:
        model = repos.model_registry.get_champion(feature_set_id, label_definition_id)
        return None if model is None else {"model_id": model.model_id, "status": model.status}
    finally:
        repos.close()


@router.get("/improvement-report")
def improvement_report():
    """Return read-only candidate recommendations; never promote a model."""
    repos = RepositoryFactory()
    try:
        return ModelImprovementService().build_report(repos.model_registry.get_all())
    finally:
        repos.close()


@router.get("/experiment-plan")
def experiment_plan(
    bars: int = 1_000,
    horizon_candles: int = 12,
    up_return_threshold: float = 0.003,
    n_estimators: int = 100,
    max_depth: int = 3,
    learning_rate: float = 0.05,
    probability_threshold: float = 0.50,
):
    """Suggest bounded training variations. This route does not start a job."""
    return ModelExperimentService().plan(locals())


@router.get("/health")
def model_health():
    """Report champion feature drift without changing any model state."""
    try:
        return ModelHealthService().check()
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/{model_id}/review-guidance")
def review_guidance(model_id: str):
    repos = RepositoryFactory()
    try:
        model = repos.model_registry.get(model_id)
        if model is None:
            raise HTTPException(status_code=404, detail="model not found")
        result = ModelReviewGuidanceService().review(model)
        repos.model_registry.add_review_event(model_id, "ai_guidance", result)
        return result
    finally:
        repos.close()


@router.get("/{model_id}/review-history")
def review_history(model_id: str):
    repos = RepositoryFactory()
    try:
        try:
            return repos.model_registry.review_history(model_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
    finally:
        repos.close()


@router.post("/{model_id}/promote")
def promote(model_id: str, request: dict):
    if not request.get("reviewer") or not request.get("rationale"):
        raise HTTPException(status_code=400, detail="reviewer and rationale are required")
    repos = RepositoryFactory()
    try:
        model = repos.model_registry.promote_candidate(model_id, request["reviewer"], request["rationale"])
        return {"model_id": model.model_id, "status": model.status}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    finally:
        repos.close()


@router.post("/{model_id}/rollback")
def rollback(model_id: str, request: dict):
    if not request.get("reviewer") or not request.get("rationale"):
        raise HTTPException(status_code=400, detail="reviewer and rationale are required")
    repos = RepositoryFactory()
    try:
        model = repos.model_registry.rollback(model_id, request["reviewer"], request["rationale"])
        return {"model_id": model.model_id, "status": model.status}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    finally:
        repos.close()


@router.delete("/{model_id}")
def delete_model(model_id: str, request: dict):
    if not request.get("reviewer") or not request.get("rationale"):
        raise HTTPException(status_code=400, detail="reviewer and rationale are required")
    repos = RepositoryFactory()
    try:
        artifact_path = repos.model_registry.delete_model(
            model_id, request["reviewer"], request["rationale"]
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        repos.close()

    _remove_model_artifacts(artifact_path)
    return {"model_id": model_id, "deleted": True}


def _remove_model_artifacts(artifact_path: str):
    """Delete only local artifacts managed by this application."""
    root = Path("data/model_artifacts").resolve()
    artifact = Path(artifact_path).resolve()
    if root not in artifact.parents:
        logger.warning("Refusing to delete model artifact outside %s: %s", root, artifact)
        return
    for path in (artifact, artifact.with_suffix(".json")):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove model artifact: %s", path, exc_info=True)
