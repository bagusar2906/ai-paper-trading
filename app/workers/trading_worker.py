import logging
import time

from app.config import WorkerConfig
from app.engine.factory import create_engine


logger = logging.getLogger(__name__)


class TradingWorker:

    def __init__(self):
        self.engine = create_engine()

    def run_once(self):
        return self.engine.run_once()

    def run(self):

        logger.info("Trading worker started")

        try:

            while True:

                try:
                    result = self.run_once()

                    logger.info(result.message)

                except Exception:
                    logger.exception("Trading cycle failed")

                time.sleep(WorkerConfig.INTERVAL_SECONDS)

        finally:

            self.engine.close()

    def close(self):
        self.engine.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    TradingWorker().run()