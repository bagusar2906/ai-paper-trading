"""Candidate-only retraining hook; execution is injected by the host scheduler."""


class CandidateRetrainingJob:
    def __init__(self, train_candidate):
        self.train_candidate = train_candidate

    def run(self):
        result = self.train_candidate()
        if result.status != "candidate":
            raise ValueError("scheduled retraining may only create a candidate")
        return result


class ModelMonitoringJob:
    """Host-scheduler hook that records a health recommendation, never retrains."""

    def __init__(self, check_health, repository_factory):
        self.check_health = check_health
        self.repository_factory = repository_factory

    def run(self):
        report = self.check_health()
        model_id = report.get("model_id")
        if not model_id:
            return report
        repos = self.repository_factory()
        try:
            repos.model_registry.add_review_event(model_id, "monitoring_recommendation", report)
        finally:
            repos.close()
        return report
