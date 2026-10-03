from app.backtest.job_manager import JobManager


def test_failed_backtest_marks_job_finished_with_error():
    manager = JobManager()
    job_id = manager.create()

    manager.fail(job_id, ValueError("OmniRoute timed out"))

    job = manager.get(job_id)
    assert job["finished"] is True
    assert job["failed"] is True
    assert "OmniRoute timed out" in job["status"]


def test_stop_request_marks_job_for_cooperative_cancellation():
    manager = JobManager()
    job_id = manager.create()

    manager.request_cancel(job_id)
    manager.complete(job_id, result={"partial": True}, cancelled=True)

    job = manager.get(job_id)
    assert job["cancel_requested"] is True
    assert job["cancelled"] is True
    assert job["status"] == "Stopped — showing partial results"


def test_cancel_endpoint_requests_stop(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import backtest

    manager = JobManager()
    job_id = manager.create()
    monkeypatch.setattr(backtest, "job_manager", manager)
    app = FastAPI()
    app.include_router(backtest.router)

    response = TestClient(app).post(f"/backtest/cancel/{job_id}")

    assert response.status_code == 200
    assert response.json()["cancel_requested"] is True
