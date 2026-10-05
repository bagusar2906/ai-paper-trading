"""Daily, recommendation-only monitoring for champion models."""

import logging
import threading

from app.factories.repository_factory import RepositoryFactory
from app.ml.scheduler import ModelMonitoringJob
from app.services.model_health_service import ModelHealthService

logger = logging.getLogger(__name__)


class DailyModelMonitoringScheduler:
    """Runs a safe health check at startup and then once per day."""

    def __init__(self, job_factory=None, interval_seconds: int = 24 * 60 * 60):
        self.job_factory = job_factory or self._default_job
        self.interval_seconds = interval_seconds
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()

    @staticmethod
    def _default_job():
        return ModelMonitoringJob(ModelHealthService().check, RepositoryFactory)

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop_event.set()

    def run_once(self):
        """Run only monitoring and audit recording; no model action is possible here."""
        try:
            report = self.job_factory().run()
            logger.info("Daily model monitoring completed: %s", report.get("recommendation", report.get("status")))
            return report
        except Exception:
            logger.exception("Daily model monitoring failed")
            return None

    def _loop(self):
        self.run_once()
        while self._running and not self._stop_event.wait(self.interval_seconds):
            self.run_once()
