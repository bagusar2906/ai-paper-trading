from app.enums.signal_action import SignalAction


class RiskManager:

    MAX_OPEN_POSITIONS = 3

    def can_open_position(
        self,
        signal,
        account,
        positions,
    ):

        if signal.action == SignalAction.HOLD:
            return False

        if len(positions) >= self.MAX_OPEN_POSITIONS:
            return False

        return True