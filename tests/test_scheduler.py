from unittest.mock import patch

from app.scheduler.trading_scheduler import TradingScheduler


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
