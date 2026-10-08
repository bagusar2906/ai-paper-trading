import numpy as np
import pytest

from app.database.models import ModelPromotionEntity, ModelVersionEntity
from app.ml.monitoring import drift_status, population_stability_index
from app.ml.scheduler import CandidateRetrainingJob, ModelMonitoringJob


def test_drift_monitoring_flags_material_distribution_shift():
    reference = np.linspace(0, 1, 100)
    current = np.linspace(5, 6, 100)
    assert drift_status(population_stability_index(reference, current)) == "drifted"


def test_candidate_retraining_job_refuses_non_candidates():
    class Result:
        status = "champion"
    with pytest.raises(ValueError, match="candidate"):
        CandidateRetrainingJob(lambda: Result()).run()


def test_monitoring_job_records_recommendation_without_retraining(repos):
    repos.session.add(ModelVersionEntity(
        model_id="monitoring-champion", training_run_id="monitoring-run", status="champion",
        artifact_path="model.pkl", artifact_sha256="a" * 64,
        feature_set_id="core-v1", label_definition_id="future-return-up",
        metrics_json="{}", metadata_json="{}",
    ))
    repos.session.commit()

    report = ModelMonitoringJob(
        lambda: {"model_id": "monitoring-champion", "recommendation": "plan_retraining"},
        lambda: repos,
    ).run()

    history = repos.model_registry.review_history("monitoring-champion")
    assert report["recommendation"] == "plan_retraining"
    assert history[-1]["type"] == "monitoring_recommendation"


@pytest.mark.parametrize("enabled", [True, False])
def test_monitoring_event_reports_saved_self_training_setting(repos, monkeypatch, enabled):
    import json
    from app.services.model_health_service import ModelHealthService

    monkeypatch.setattr(repos, "close", lambda: None)
    repos.session.add(ModelVersionEntity(
        model_id="monitoring-champion", training_run_id="monitoring-run", status="champion",
        artifact_path="model.pkl", artifact_sha256="a" * 64,
        feature_set_id="core-v1", label_definition_id="future-return-up",
        metrics_json="{}", metadata_json="{}",
    ))
    repos.session.commit()
    repos.settings.set("model_self_training_config", json.dumps({"enabled": enabled}))
    service = ModelHealthService(repository_factory=lambda: repos)

    report = ModelMonitoringJob(service.check, lambda: repos).run()

    assert report["automatic_retraining"] is enabled
    history = repos.model_registry.review_history("monitoring-champion")
    assert history[-1]["type"] == "monitoring_recommendation"
    assert history[-1]["evidence"]["automatic_retraining"] is enabled


def test_model_registry_deletes_non_champion_and_records_audit(repos):
    repos.session.add(ModelVersionEntity(
        model_id="candidate-delete-test",
        training_run_id="train-delete-test",
        status="candidate",
        artifact_path="data/model_artifacts/candidate-delete-test.pkl",
        artifact_sha256="a" * 64,
        feature_set_id="core-v1",
        label_definition_id="future-return-up",
        metrics_json="{}",
        metadata_json="{}",
    ))
    repos.session.commit()

    artifact_path = repos.model_registry.delete_model(
        "candidate-delete-test", "reviewer", "no longer needed"
    )

    assert artifact_path.endswith("candidate-delete-test.pkl")
    assert repos.model_registry.get("candidate-delete-test") is None
    audit = repos.session.query(ModelPromotionEntity).one()
    assert audit.action == "delete"
    assert audit.reviewer == "reviewer"


def test_model_registry_deletes_champion_and_records_audit(repos):
    repos.session.add(ModelVersionEntity(
        model_id="champion-delete-test",
        training_run_id="train-champion-test",
        status="champion",
        artifact_path="data/model_artifacts/champion-delete-test.pkl",
        artifact_sha256="b" * 64,
        feature_set_id="core-v1",
        label_definition_id="future-return-up",
        metrics_json="{}",
        metadata_json="{}",
    ))
    repos.session.commit()

    repos.model_registry.delete_model("champion-delete-test", "reviewer", "retired from use")

    assert repos.model_registry.get("champion-delete-test") is None
    audit = repos.session.query(ModelPromotionEntity).one()
    assert audit.action == "delete"
