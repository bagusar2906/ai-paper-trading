"""Candidate-only retraining hook; execution is injected by the host scheduler."""


class CandidateRetrainingJob:
    def __init__(self, train_candidate):
        self.train_candidate = train_candidate

    def run(self):
        result = self.train_candidate()
        if result.status != "candidate":
            raise ValueError("scheduled retraining may only create a candidate")
        return result
