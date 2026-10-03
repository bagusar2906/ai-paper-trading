from app.backtest.job_manager import JobManager


def test_failed_backtest_marks_job_finished_with_error():
    manager = JobManager()
    job_id = manager.create()

    manager.fail(job_id, ValueError("OmniRoute timed out"))

    job = manager.get(job_id)
    assert job["finished"] is True
    assert job["failed"] is True
    assert "OmniRoute timed out" in job["status"]
