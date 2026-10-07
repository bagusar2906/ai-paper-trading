"""Opt-in, app-lifetime retraining that can only create offline candidates."""

from datetime import datetime, timedelta, timezone
import json
import logging
import threading
import time

from app.factories.repository_factory import RepositoryFactory
from app.services.model_training_service import ModelTrainingService

logger = logging.getLogger(__name__)


class SelfTrainingScheduler:
    CONFIG_KEY = "model_self_training_config"
    STATUS_KEY = "model_self_training_status"

    def __init__(self, repository_factory=RepositoryFactory, trainer_factory=ModelTrainingService):
        self.repository_factory = repository_factory
        self.trainer_factory = trainer_factory
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._run_lock = threading.Lock()
        self._thread = None
        self._next_attempt = 0
        self._revision = 0

    def _read(self, key, default):
        repos = self.repository_factory()
        try:
            try:
                value = json.loads(repos.settings.get(key, json.dumps(default)))
            except (TypeError, json.JSONDecodeError):
                return default
            return value if isinstance(value, dict) else default
        finally:
            repos.close()

    def _write(self, key, value):
        repos = self.repository_factory()
        try:
            repos.settings.set(key, json.dumps(value, allow_nan=False))
        finally:
            repos.close()

    def configuration(self):
        return self._read(self.CONFIG_KEY, {"enabled": False, "interval_minutes": 60, "training": {"feature_set_id": "raw-ohlcv-v1"}})

    def status(self):
        running = self._run_lock.locked()
        last_run = self._read(self.STATUS_KEY, {})
        if not running and last_run.get("status") == "running":
            last_run = {**last_run, "status": "interrupted"}
        return {"configuration": self.configuration(),
                "last_run": last_run,
                "running": running,
                "automatic_promotion": False}

    def configure(self, request):
        if not isinstance(request.get("enabled"), bool):
            raise ValueError("enabled must be a boolean")
        current = self.configuration()
        if not request["enabled"]:
            current["enabled"] = False
        else:
            interval = request.get("interval_minutes", 60)
            if isinstance(interval, bool) or not isinstance(interval, int) or not 5 <= interval <= 1440:
                raise ValueError("interval_minutes must be an integer between 5 and 1440")
            parameters = request.get("training", {})
            if not isinstance(parameters, dict):
                raise ValueError("training must be an object")
            parameters = {"feature_set_id": "raw-ohlcv-v1", "replace_previous_candidate": True, **parameters}
            current = {"enabled": True, "interval_minutes": interval,
                       "training": ModelTrainingService().validate_request(parameters)}
        self._write(self.CONFIG_KEY, current)
        self._revision += 1
        self._next_attempt = 0
        self._wake.set()
        return self.status()

    def run_once(self):
        if not self._run_lock.acquire(blocking=False):
            return {"status": "busy"}
        try:
            config = self.configuration()
            revision = self._revision
            if not config.get("enabled"):
                return {"status": "disabled"}
            started = datetime.now(timezone.utc).isoformat()
            self._write(self.STATUS_KEY, {"status": "running", "started_at": started})
            try:
                result = self.trainer_factory().train_candidate(config["training"], backfill=True)
                if result.get("status") not in {"candidate", "duplicate"}:
                    raise ValueError("Self-training may only create a candidate or skip unchanged inputs")
                report = {"status": "skipped_unchanged" if result["status"] == "duplicate" else "candidate_created",
                          "model_id": result.get("model_id"), "started_at": started,
                          "finished_at": datetime.now(timezone.utc).isoformat(),
                          "training": config["training"], "data_sync": result.get("data_sync"),
                          "replaced_model_ids": result.get("replaced_model_ids", []),
                          "cleanup_warnings": result.get("cleanup_warnings", [])}
            except Exception as error:
                logger.exception("Self-training attempt failed; it will retry at the next interval")
                report = {"status": "failed", "started_at": started,
                          "finished_at": datetime.now(timezone.utc).isoformat(),
                          "message": str(error)[:250]}
            interval = config["interval_minutes"] * 60
            report["next_check_at"] = (datetime.now(timezone.utc) + timedelta(seconds=interval)).isoformat()
            self._next_attempt = time.monotonic() + interval if revision == self._revision else 0
            self._write(self.STATUS_KEY, report)
            return report
        finally:
            self._run_lock.release()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._next_attempt = 0
        self._thread = threading.Thread(target=self._loop, name="model-self-training", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop.is_set():
            self._wake.clear()
            if time.monotonic() >= self._next_attempt:
                try:
                    self.run_once()
                except Exception:
                    logger.exception("Self-training settings or status could not be accessed")
            self._wake.wait(timeout=30)


self_training_scheduler = SelfTrainingScheduler()
