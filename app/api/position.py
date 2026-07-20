from dataclasses import asdict

from fastapi import APIRouter


from app.models.position.update_position_request import UpdatePositionRequest
from app.services.position_service import PositionService

router = APIRouter()


@router.put("/positions/{position_id}")
def update_position(position_id: int, request: UpdatePositionRequest):

    response = PositionService().update_position(
        position_id,
        request,
    )

    return asdict(response)