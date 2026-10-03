from unittest.mock import patch

from app.scheduler.trading_scheduler import TradingScheduler
from app.scheduler.candle_schedule import seconds_until_next_candle


def test_scheduler_waits_for_the_next_candle_boundary():
    assert seconds_until_next_candle("M5", now=601, grace_seconds=3) == 302
    assert seconds_until_next_candle("15m", now=1800, grace_seconds=3) == 903


def test_scheduler_closes_engine_after_each_cycle():

    class Engine:

        closed = False

        def run_once(self):
            scheduler._running = False

        def close(self):
            self.closed = True

    scheduler = TradingScheduler()
    scheduler._running = True
    engine = Engine()

    with (
        patch(
            "app.scheduler.trading_scheduler.create_engine",
            return_value=engine,
        ),
        patch("app.scheduler.trading_scheduler.time.sleep"),
    ):
        scheduler._loop()

    assert engine.closed
