"""Helpers for running one trading cycle per completed candle."""

import time


_TIMEFRAME_SECONDS = {
    "M1": 60, "1m": 60,
    "M5": 300, "5m": 300,
    "M15": 900, "15m": 900,
    "M30": 1800, "30m": 1800,
    "H1": 3600, "1h": 3600,
    "H4": 14400, "4h": 14400,
    "D1": 86400, "1d": 86400,
}


def seconds_until_next_candle(timeframe, now=None, grace_seconds=3):
    """Return seconds to the next candle boundary plus a short API grace."""
    interval = _TIMEFRAME_SECONDS.get(timeframe)
    if interval is None:
        raise ValueError(f"Unsupported scheduler timeframe: {timeframe}")

    now = time.time() if now is None else now
    next_boundary = (int(now // interval) + 1) * interval
    return max(1, next_boundary - now + grace_seconds)
