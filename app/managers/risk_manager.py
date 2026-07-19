class RiskManager:

    def can_open_position(
        self,
        signal,
        account,
        positions,
    ) -> bool:

        if signal.action.name == "HOLD":
            return False

        if len(positions) >= 3:
            return False

        return True