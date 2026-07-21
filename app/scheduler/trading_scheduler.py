import threading
import time

from app.factories.engine_factory import create_engine



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

        engine = create_engine()

        while self._running:

            try:

                engine.run_once()

            except Exception as ex:

                print(ex)

            time.sleep(5)