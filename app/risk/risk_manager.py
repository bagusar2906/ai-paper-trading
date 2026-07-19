from dataclasses import dataclass

from app.enums.signal_action import SignalAction
from app.risk.position_sizer import PositionSizer


@dataclass
class RiskDecision:

    allowed: bool
    quantity: float = 0.0
    reason: str = ""


class RiskManager:

    def __init__(self):

        self.position_sizer = PositionSizer()

        #
        # Configurable limits
        #
        self.max_open_positions = 5
        self.risk_percent = 1.0

    def evaluate(
        self,
        signal,
        account,
        positions,
    ) -> RiskDecision:

        #
        # Ignore HOLD
        #
        if signal.action == SignalAction.HOLD:

            return RiskDecision(
                allowed=False,
                reason="HOLD signal",
            )

        #
        # Position already exists
        #
        if any(
            p.symbol == signal.symbol
            for p in positions
        ):

            return RiskDecision(
                allowed=False,
                reason=f"Position already exists for {signal.symbol}",
            )

        #
        # Maximum open positions
        #
        if len(positions) >= self.max_open_positions:

            return RiskDecision(
                allowed=False,
                reason="Maximum open positions reached",
            )

        #
        # Stop loss required
        #
        if signal.stop_loss is None:

            return RiskDecision(
                allowed=False,
                reason="Signal has no stop loss",
            )

        stop_distance = abs(
            signal.price
            - signal.stop_loss
        )

        if stop_distance <= 0:

            return RiskDecision(
                allowed=False,
                reason="Invalid stop loss distance",
            )

        quantity = self.position_sizer.calculate(
            account=account,
            risk_percent=self.risk_percent,
            stop_loss_distance=stop_distance,
        )

        if quantity <= 0:

            return RiskDecision(
                allowed=False,
                reason="Calculated quantity is zero",
            )

        return RiskDecision(
            allowed=True,
            quantity=quantity,
            reason="Approved",
        )