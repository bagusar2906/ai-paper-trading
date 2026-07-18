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

        while True:

            try:

                result = self.run_once()

                logger.info(result.message)

                if result.signal:

                    logger.info(
                        "[%s] %s @ %.2f",
                        result.signal.symbol,
                        result.signal.action,
                        result.signal.price,
                    )

            except Exception:

                logger.exception("Trading cycle failed")

            time.sleep(WorkerConfig.INTERVAL_SECONDS)