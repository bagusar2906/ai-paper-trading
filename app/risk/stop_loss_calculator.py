from app.enums.signal_action import SignalAction


class StopLossCalculator:

    def fixed(
        self,
        signal,
        distance,
    ):

        if signal.action == SignalAction.BUY:

            return signal.price - distance

        if signal.action == SignalAction.SELL:

            return signal.price + distance

        return None