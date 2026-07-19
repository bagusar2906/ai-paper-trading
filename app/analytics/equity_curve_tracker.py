from app.analytics.equity_point import EquityPoint


class EquityCurveTracker:

    def __init__(self):

        self._points = []

    def record(self, time, account):

        self._points.append(
            EquityPoint(
                time=time,
                balance=account.balance,
                equity=account.equity,
            )
        )

    def get_curve(self):

        return list(self._points)

    def clear(self):

        self._points.clear()