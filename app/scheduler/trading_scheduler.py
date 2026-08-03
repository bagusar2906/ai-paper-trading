import logging
import threading
import time

from app.factories.engine_factory import create_engine

logger = logging.getLogger(__name__)


class TradingScheduler:

    def __init__(self):

        self._running = False
        self._thread = None

    def start(self):

        if self._running:
            return

        self._running = True

        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
        )

        self._thread.start()

    def stop(self):

        self._running = False

    def _loop(self):

        while self._running:

            try:

                engine = create_engine()

                if engine is None:

                    logger.info(
                        "No active strategy configured."
                    )

                    time.sleep(5)

                    continue

                engine.run_once()

            except Exception:

                logger.exception(
                    "Trading scheduler failed."
                )

            time.sleep(5)