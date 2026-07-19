from app.models.account import Account


class PositionSizer:

    def calculate(
        self,
        account: Account,
        risk_percent: float,
        stop_loss_distance: float,
        pip_value: float = 1.0,
    ) -> float:

        if stop_loss_distance <= 0:
            return 0.0

        risk_amount = (
            account.balance
            * risk_percent
            / 100
        )

        quantity = (
            risk_amount
            / (stop_loss_distance * pip_value)
        )

        return round(quantity, 2)