from app.scheduler.model_monitoring_scheduler import DailyModelMonitoringScheduler


def test_daily_monitoring_scheduler_runs_a_recommendation_only_job():
    calls = []

    class Job:
        def run(self):
            calls.append("run")
            return {"recommendation": "continue_monitoring"}

    scheduler = DailyModelMonitoringScheduler(job_factory=lambda: Job())

    report = scheduler.run_once()

    assert calls == ["run"]
    assert report["recommendation"] == "continue_monitoring"


def test_daily_monitoring_scheduler_survives_a_failed_check():
    class Job:
        def run(self):
            raise RuntimeError("provider unavailable")

    scheduler = DailyModelMonitoringScheduler(job_factory=lambda: Job())

    assert scheduler.run_once() is None
