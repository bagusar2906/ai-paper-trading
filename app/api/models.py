import json
import logging

from fastapi import APIRouter, HTTPException

from app.factories.repository_factory import RepositoryFactory
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


@router.get("/champion")
def champion(feature_set_id: str, label_definition_id: str):
    repos = RepositoryFactory()
    try:
        model = repos.model_registry.get_champion(feature_set_id, label_definition_id)
        return None if model is None else {"model_id": model.model_id, "status": model.status}
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
