from dataclasses import asdict

from fastapi import APIRouter

from app.services.dashboard_service import DashboardService

router = APIRouter()

service = DashboardService()


@router.get("/dashboard")
def dashboard():

    return asdict(
        service.get_dashboard()
    )