import json
import logging
from pathlib import Path

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
            # Context is non-secret provenance used only to prevent a
            # candidate comparison from silently using a different market.
            "market_context": _market_context(getattr(item, "metadata_json", None)),
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
