from fastapi import APIRouter
from fastapi import HTTPException

from app.factories.repository_factory import RepositoryFactory
from app.strategy.strategy_catalog import CATALOG
from app.strategy.strategy_request import StrategyRequest
from app.strategy.strategy_service import StrategyService
from app.factories.strategy_factory import (
    get_strategy_schema,
    get_supported_strategies,
)

router = APIRouter(
    prefix="/strategy",
    tags=["Strategy"],
)


def create_service():

    repos = RepositoryFactory()

    service = StrategyService(repos)

    return repos, service


@router.get("")
def get_all():

    repos, service = create_service()

    try:

        return service.get_all()

    finally:

        repos.close()


@router.get("/{strategy_id}")
def get(strategy_id: int):

    repos, service = create_service()

    try:

        strategy = service.get(strategy_id)

        if strategy is None:

            raise HTTPException(
                status_code=404,
                detail="Strategy not found",
            )

        return strategy

    finally:

        repos.close()


@router.post("")
def create(request: StrategyRequest):

    repos, service = create_service()

    try:

        return service.create(request)

    finally:

        repos.close()


@router.put("/{strategy_id}")
def update(
    strategy_id: int,
    request: StrategyRequest,
):

    repos, service = create_service()

    try:

        strategy = service.update(
            strategy_id,
            request,
        )

        if strategy is None:

            raise HTTPException(
                status_code=404,
                detail="Strategy not found",
            )

        return strategy

    finally:

        repos.close()


@router.delete("/{strategy_id}")
def delete(strategy_id: int):

    repos, service = create_service()

    try:

        strategy = service.get(strategy_id)

        if strategy is None:

            raise HTTPException(
                status_code=404,
                detail="Strategy not found",
            )

        service.delete(strategy_id)

        return {
            "success": True,
            "message": "Strategy deleted successfully",
        }

    finally:

        repos.close()

@router.get("/catalog")
def get_catalog():

    return CATALOG

@router.get("/types")
def get_types():

    return get_supported_strategies()


@router.get("/schema/{strategy_type}")
def get_schema(strategy_type: str):

    return get_strategy_schema(strategy_type)