import json

from fastapi import APIRouter

from app.api.services.strategy_profile_service import StrategyProfileService

router = APIRouter(
    prefix="/strategy-profiles",
    tags=["Strategy Profiles"],
)

service = StrategyProfileService()


#
# GET ALL
#
@router.get("")
def get_profiles():

    profiles = service.get_all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "strategy": p.strategy,
        }
        for p in profiles
    ]


#
# GET ONE
#
@router.get("/{profile_id}")
def get_profile(profile_id: int):

    profile = service.get(profile_id)

    if profile is None:
        return {"error": "Profile not found"}

    return {
        "id": profile.id,
        "name": profile.name,
        "strategy": profile.strategy,
        "parameters": json.loads(profile.parameters_json),
    }


#
# CREATE
#
@router.post("")
def create_profile(request: dict):

    profile = service.create(
        request["name"],
        request["strategy"],
        request["parameters"],
    )

    return {
        "id": profile.id,
    }


#
# UPDATE
#
@router.put("/{profile_id}")
def update_profile(profile_id: int, request: dict):

    profile = service.update(
        profile_id,
        request["parameters"],
    )

    if profile is None:
        return {"error": "Profile not found"}

    return {"success": True}


#
# DELETE
#
@router.delete("/{profile_id}")
def delete_profile(profile_id: int):

    service.delete(profile_id)

    return {"success": True}