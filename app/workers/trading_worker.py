import logging
import time

from app.config import WorkerConfig
from app.factories.engine_factory import create_engine


logger = logging.getLogger(__name__)


class TradingWorker:

    def __init__(self):

        self.engine = None

    def run_once(self):

        #
        # Reload engine so strategy changes are picked up automatically.
        #

        # The engine owns a PaperBroker and its database session.  Close the
        # previous cycle's engine before replacing it so long-running workers
        # do not accumulate checked-out SQLAlchemy connections.
        if self.engine is not None:
            self.engine.close()
            self.engine = None

        self.engine = create_engine()

        if self.engine is None:

            logger.info(
                "No active strategy configured."
            )

            return None

        return self.engine.run_once()

    def run(self):

        logger.info(
            "Trading worker started"
        )

        try:

            while True:

                try:

                    result = self.run_once()

                    if result is not None:

                        logger.info(
                            result.message
                        )

                except Exception:

                    logger.exception(
                        "Trading cycle failed"
                    )

                time.sleep(
                    WorkerConfig.INTERVAL_SECONDS
                )

        finally:

            if self.engine is not None:

                self.engine.close()

    def close(self):

        if self.engine is not None:

            self.engine.close()


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO
    )

    TradingWorker().run()
