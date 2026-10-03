import numpy as np
import pytest

from app.ml.monitoring import drift_status, population_stability_index
from app.ml.scheduler import CandidateRetrainingJob


def test_drift_monitoring_flags_material_distribution_shift():
    reference = np.linspace(0, 1, 100)
    current = np.linspace(5, 6, 100)
    assert drift_status(population_stability_index(reference, current)) == "drifted"


def test_candidate_retraining_job_refuses_non_candidates():
    class Result:
        status = "champion"
    with pytest.raises(ValueError, match="candidate"):
        CandidateRetrainingJob(lambda: Result()).run()
