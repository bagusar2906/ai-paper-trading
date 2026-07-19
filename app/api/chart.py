from dataclasses import asdict

from fastapi import APIRouter

from app.services.chart_service import ChartService

router = APIRouter()

service = ChartService()


@router.get("/chart")
def chart():

    return asdict(
        service.get_chart()
    )