from app.services.model_experiment_service import ModelExperimentService


def test_plan_is_bounded_and_never_starts_training():
    plan = ModelExperimentService().plan({"n_estimators": 900, "max_depth": 0, "learning_rate": 2})

    assert plan["automatic_training"] is False
    assert plan["automatic_promotion"] is False
    assert plan["baseline"]["n_estimators"] == 500
    assert plan["baseline"]["max_depth"] == 1
    assert plan["baseline"]["learning_rate"] == 0.30
    assert len(plan["experiments"]) == 3


def test_plan_keeps_experiment_parameters_inside_bounds():
    plan = ModelExperimentService().plan({"n_estimators": 500, "max_depth": 8, "learning_rate": 0.01})

    for experiment in plan["experiments"]:
        parameters = experiment["parameters"]
        assert 25 <= parameters["n_estimators"] <= 500
        assert 1 <= parameters["max_depth"] <= 8
        assert 0.01 <= parameters["learning_rate"] <= 0.30
