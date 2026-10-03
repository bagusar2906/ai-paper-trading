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
    ):

        job = self.jobs[job_id]

        job["progress"] = 100
        job["status"] = "Completed"

        job["finished"] = True
        job["result"] = result

    def fail(self, job_id, error):

        job = self.jobs[job_id]

        job["status"] = f"Failed: {str(error)[:250]}"
        job["finished"] = True
        job["failed"] = True

    def get(self, job_id):

        return self.jobs.get(job_id)


job_manager = JobManager()
