from dataclasses import asdict

from app.models.position.order_response import OrderResponse
from app.repositories.factory import RepositoryFactory


class PositionService:

    def update_position(
        self,
        position_id: int,
        request,
    ):

        repos = RepositoryFactory()

        try:

            position = repos.positions.get_by_id(position_id)

            if position is None:

                return OrderResponse(
                    success=False,
                    message="Position not found.",
                )

            position.stop_loss = request.stop_loss
            position.take_profit = request.take_profit

            repos.positions.update(position)

            return OrderResponse(
                success=True,
                message="Position updated successfully.",
            )

        finally:

            repos.close()