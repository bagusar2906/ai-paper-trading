from dataclasses import asdict

from fastapi import APIRouter

from app.models.position.order_request import OrderRequest
from app.services.order_service import OrderService

router = APIRouter()

service = OrderService()


@router.post("/orders")
def place_order(request: OrderRequest):

    result = service.place_order(request)

    return asdict(result)
