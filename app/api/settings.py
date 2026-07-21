from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from app.models.settings.settings_request import SettingsRequest
from app.services.settings_service import SettingsService

router = APIRouter()

service = SettingsService()


@router.get("/settings")
def get_settings():

    return asdict(service.get_settings())


@router.put("/settings")
def update_settings(request: SettingsRequest):

    try:
        result = service.update_settings(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return asdict(result)
