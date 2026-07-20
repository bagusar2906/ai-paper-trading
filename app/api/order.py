from dataclasses import asdict

from fastapi import APIRouter

from app.models.dashboard.order_request import OrderRequest
from app.services.order_service import OrderService

router = APIRouter()

service = OrderService()


@router.get("/orders")
def place_order(request: OrderRequest):

    return asdict(
        service.place_order(request)
    )