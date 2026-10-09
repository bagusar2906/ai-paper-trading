from pathlib import Path

import pandas as pd
import pytest

from app.services.fresh_model_validation_service import FreshModelValidationService
from app.services.model_training_service import ModelTrainingService
from app.services.training_coach_evidence import fresh_boundary
from tests.test_controlled_model_experiments import setup_service
from tests.test_ml_candidate_training import _candles


def test_frozen_models_use_disjoint_fresh_periods_and_coached_replays_wait(tmp_path, repos, monkeypatch):
    service, selected, _, provider, _, training, _ = setup_service(tmp_path, repos, monkeypatch)
    experiment = service.run(selected)
    original = {row["model_id"]: Path(repos.model_registry.get(row["model_id"]).artifact_path).read_bytes() for row in experiment["results"]}
    validator = FreshModelValidationService(lambda *_: provider, lambda: repos)
    waiting = validator.validate(experiment)
    assert waiting["status"] == "waiting_for_fresh_data" and waiting["samples"] == 0
    monkeypatch.setattr(provider, "get_history", lambda *_: _candles(900).tail(700))
    validation = validator.validate(experiment)
    assert validation["status"] == "completed", validation
    assert pd.Timestamp(validation["evaluation_start"]) > pd.Timestamp(experiment["outcome_end_time"])
    assert validation["baseline"]["up"]["probability"] == experiment["baseline"]["up"]["probability"]
    assert validation["baseline"]["down"]["probability"] == experiment["baseline"]["down"]["probability"]
    assert len(training) == 4  # fresh validation never retrains
    for model_id, payload in original.items():
        assert Path(repos.model_registry.get(model_id).artifact_path).read_bytes() == payload
    # The service re-reads persisted boundaries under its lock even when a
    # caller omits earlier validation reports.
    repeated = validator.validate(experiment)
    assert repeated["status"] == "waiting_for_fresh_data" and repeated["samples"] == 0
    plan = service.plan(selected)
    plan.update(coach_id="saved-coach", fresh_after=experiment["outcome_end_time"])
    repeated_plan = service.run(selected, plan=plan)
    assert repeated_plan["status"] == "waiting_for_fresh_data"
    assert len(training) == 4
    monkeypatch.setattr(provider, "get_history", lambda *_: _candles(1000).tail(700))
    next_experiment = service.run(selected, plan=plan)
    assert next_experiment["status"] == "completed", next_experiment
    assert pd.Timestamp(next_experiment["evaluation_start"]) > pd.Timestamp(validation["outcome_end_time"])
    assert len(training) == 8
    assert service.run(selected, plan=plan)["status"] == "waiting_for_fresh_data"
    assert len(training) == 8
    assert repos.model_registry.get(selected).status == "champion"
    assert not ModelTrainingService._training_lock.locked()


def test_corrupt_artifact_is_reported_and_other_models_still_validate(tmp_path, repos, monkeypatch):
    service, selected, _, provider, _, _, _ = setup_service(tmp_path, repos, monkeypatch)
    experiment = service.run(selected)
    victim = experiment["results"][0]["model_id"]
    artifact = Path(repos.model_registry.get(victim).artifact_path)
    artifact.write_bytes(b"corrupt local artifact")
    monkeypatch.setattr(provider, "get_history", lambda *_: _candles(900).tail(700))
    report = FreshModelValidationService(lambda *_: provider, lambda: repos).validate(experiment)
    assert report["status"] == "partial"
    failure = next(row for row in report["results"] if row["model_id"] == victim)
    assert failure["status"] == "failed" and "checksum" in failure["error"]
    assert len([row for row in report["results"] if row["status"] == "completed"]) == 3
    assert report["history_saved"]


def test_boundary_uses_actual_label_prices_across_market_gaps():
    history = pd.DataFrame(index=pd.DatetimeIndex(["2026-01-02T22:00:00Z", "2026-01-02T22:05:00Z",
        "2026-01-05T00:00:00Z", "2026-01-05T00:05:00Z", "2026-01-05T00:10:00Z"]))
    report = {"evaluation_end": "2026-01-02T22:00:00Z", "purge_candles": 3,
              "market_context": {"timeframe": "M5"}}
    assert fresh_boundary(report, history) == history.index[3]


@pytest.mark.parametrize("changed", [{"symbol": "OTHER"}, {"up_return_threshold": .01},
                                    {"probability_threshold": .4}, {"bars": 1000}])
def test_custom_recipes_cannot_change_the_shared_comparison_contract(changed):
    settings = {"symbol": "XAUUSD", "timeframe": "M5", "data_source": "yahoo", "bars": 5000,
                "horizon_candles": 12, "up_return_threshold": .003, "probability_threshold": .5}
    plan = {"model_id": "m", "parameters": settings,
            "variants": [{"id": "reference", "parameters": settings}, {"id": "altered", "parameters": settings | changed}]}
    from app.services.controlled_model_experiment_service import ControlledModelExperimentService
    with pytest.raises(ValueError, match="must share"):
        ControlledModelExperimentService._validate_plan("m", plan)
