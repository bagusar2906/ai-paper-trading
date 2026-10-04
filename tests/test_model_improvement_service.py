import json
from types import SimpleNamespace

from app.services.model_improvement_service import ModelImprovementService


def _model(model_id, status, metrics, context={"symbol": "XAUUSD", "timeframe": "M5"}, folds=()):
    return SimpleNamespace(
        model_id=model_id,
        status=status,
        feature_set_id="core-v1",
        label_definition_id="future-return-up",
        metrics_json=json.dumps(metrics),
        metadata_json=json.dumps({"market_context": context, "folds": list(folds)}),
    )


def test_report_compares_compatible_candidate_with_champion():
    champion = _model("champion-1", "champion", {"roc_auc": 0.60, "brier_score": 0.22})
    candidate = _model(
        "candidate-1", "candidate", {"roc_auc": 0.66, "brier_score": 0.20},
        folds=(
            {"metrics": {"roc_auc": 0.65}},
            {"metrics": {"roc_auc": 0.67}},
        ),
    )

    report = ModelImprovementService().build_report([candidate, champion])
    assessment = report["assessments"][0]

    assert report["automatic_promotion"] is False
    assert assessment["champion_model_id"] == "champion-1"
    assert assessment["deltas"]["roc_auc"] == 0.06
    assert assessment["deltas"]["brier_score"] == 0.02
    assert assessment["recommendation"] == "paper_test"
    assert assessment["stability"]["fold_count"] == 2


def test_report_does_not_compare_different_market_contexts():
    champion = _model("champion-1", "champion", {"roc_auc": 0.70}, {"symbol": "EURUSD", "timeframe": "M5"})
    candidate = _model("candidate-1", "candidate", {"roc_auc": 0.66})

    assessment = ModelImprovementService().build_report([champion, candidate])["assessments"][0]

    assert assessment["champion_model_id"] is None
    assert assessment["recommendation"] == "paper_test"


def test_report_ranks_reviewable_candidate_with_better_validation_first():
    champion = _model("champion-1", "champion", {"roc_auc": 0.60, "brier_score": 0.22})
    stronger = _model(
        "candidate-strong", "candidate", {"roc_auc": 0.68, "brier_score": 0.20},
        folds=({"metrics": {"roc_auc": 0.67}}, {"metrics": {"roc_auc": 0.69}}),
    )
    weaker = _model(
        "candidate-weak", "candidate", {"roc_auc": 0.61, "brier_score": 0.24},
        folds=({"metrics": {"roc_auc": 0.61}}, {"metrics": {"roc_auc": 0.62}}),
    )

    assessments = ModelImprovementService().build_report([weaker, champion, stronger])["assessments"]

    assert [item["candidate_model_id"] for item in assessments] == ["candidate-strong", "candidate-weak"]
    assert [item["rank"] for item in assessments] == [1, 2]
