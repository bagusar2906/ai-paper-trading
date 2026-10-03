import uuid


class JobManager:

    def __init__(self):

        self.jobs = {}

    def create(self):

        job_id = str(uuid.uuid4())

        self.jobs[job_id] = {
            "progress": 0,
            "status": "Waiting...",
            "result": None,
            "finished": False,
            "failed": False,
            "cancel_requested": False,
            "cancelled": False,
        }

        return job_id

    def update(
        self,
        job_id,
        progress,
        status,
    ):

        job = self.jobs[job_id]

        job["progress"] = progress
        job["status"] = status

    def complete(
        self,
        job_id,
        result,
        cancelled=False,
    ):

        job = self.jobs[job_id]

        job["progress"] = 100
        job["status"] = "Stopped — showing partial results" if cancelled else "Completed"

        job["finished"] = True
        job["result"] = result
        job["cancelled"] = cancelled

    def fail(self, job_id, error):

        job = self.jobs[job_id]

        job["status"] = f"Failed: {str(error)[:250]}"
        job["finished"] = True
        job["failed"] = True

    def request_cancel(self, job_id):

        job = self.jobs.get(job_id)

        if job is None:
            return None

        if not job["finished"]:
            job["cancel_requested"] = True
            job["status"] = "Stopping after the current candle..."

        return job

    def is_cancel_requested(self, job_id):

        job = self.jobs.get(job_id)
        return bool(job and job["cancel_requested"])

    def get(self, job_id):

        return self.jobs.get(job_id)


job_manager = JobManager()
