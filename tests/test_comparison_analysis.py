import json
import math
from types import SimpleNamespace

import pandas as pd
import pytest

from app.backtest.comparison_analysis import filter_diagnostics, prediction_evidence
from app.backtest.backtest_service import BacktestService
from app.labels.future_return import FutureReturnLabel
from app.models.dashboard.dashboard_statistics import DashboardStatistics


def _history():
    return pd.DataFrame({"Close": [100, 102, 100, 102, 100]},
                        index=pd.date_range("2026-01-01", periods=5, freq="5min", tz="UTC"))


def _trace(history, probabilities, model_id="candidate"):
    return [{"time": time.isoformat(), "probability": probability,
             "model_id": model_id, "action": "HOLD", "gates": {}}
            for time, probability in zip(history.index, probabilities)]


def test_identical_actions_can_have_different_prediction_quality_and_training_baseline():
    history = _history()
    evidence = prediction_evidence(
        history, _trace(history, [.9, .1, .9, .1, .99]),
        _trace(history, [.5] * 5, "champion"), FutureReturnLabel(1, .01),
        {"prediction_baseline": {"positive_rate": .25}},
    )
    assert evidence["samples"] == 4  # last future outcome is unknown
    assert evidence["excluded_decisions"] == 1
    assert evidence["candidate"]["brier_score"] == pytest.approx(.01)
    assert evidence["champion"]["brier_score"] == pytest.approx(.25)
    assert evidence["baseline"]["brier_score"] == pytest.approx(.3125)
    assert evidence["candidate"]["roc_auc"] == 1
    assert evidence["baseline_probability"] == .25  # never fit to test rate (.5)
    assert evidence["candidate"]["probability_bins"] == [2, 0, 0, 0, 2]
    json.dumps(evidence, allow_nan=False)


def test_scoring_aligns_timestamps_and_excludes_failed_predictions():
    history = _history()
    candidate = _trace(history, [.9, .1, .9, .1, .9])
    champion = _trace(history, [.8, .2, .8, .2, .8], "champion")
    champion[1]["model_id"] = None
    evidence = prediction_evidence(history, candidate, list(reversed(champion)), FutureReturnLabel(1, .01), {})
    assert evidence["samples"] == 3
    assert evidence["baseline"] is None
    assert evidence["champion"]["brier_score"] == pytest.approx(.04)


def test_single_class_has_log_loss_but_no_auc_and_no_evidence_is_explicit():
    history = _history().iloc[:2]
    trace = _trace(history, [.9, .1])
    evidence = prediction_evidence(history, trace, trace, FutureReturnLabel(1, .01), {})
    assert evidence["candidate"]["roc_auc"] is None
    assert evidence["candidate"]["log_loss"] == pytest.approx(-math.log(.9))
    unavailable = prediction_evidence(history, [], [], FutureReturnLabel(1, .01), {})
    assert unavailable["status"] == "insufficient_evidence"
    assert unavailable["samples"] == 0


def test_filters_count_overlapping_blocks_and_execution_rejections():
    trace = [
        {"action": "HOLD", "model_id": "a", "gates": {"long_probability": True, "adx": False, "long_rsi": True, "trend_up": False}},
        {"action": "HOLD", "model_id": "a", "gates": {}},
        {"action": "HOLD", "model_id": None, "gates": {}},
        {"action": "SELL", "model_id": "a", "gates": {"short_probability": True}, "execution": {"executed": False, "reason": "Position already exists for XAUUSD"}},
    ]
    report = filter_diagnostics(trace)
    assert report["actions"] == {"BUY": 0, "SELL": 1, "HOLD": 3}
    assert report["blocked_by_filter"] == {"adx": 1, "trend_up": 1, "probability_threshold": 1}
    assert report["unavailable_predictions"] == 1
    assert report["execution_outcomes"]["Position already exists for XAUUSD"] == 1


def test_comparison_saves_json_evidence_and_reports_save_failure(monkeypatch, repos):
    history = _history()
    candidate = SimpleNamespace(model_id="a", metadata_json='{}', artifact_sha256="a" * 64, status="candidate")
    champion = SimpleNamespace(model_id="b", artifact_sha256="b" * 64)
    service = BacktestService()
    monkeypatch.setattr(service, "_load_strategy_definition", lambda _: ("AI_ASSISTED_XGB", {"horizon_candles": 1, "up_return_threshold": .01}))
    monkeypatch.setattr(service, "_comparison_models", lambda *args: (candidate, champion, history.index[0]))
    def replay(request, history, strategy, *args, **kwargs):
        return SimpleNamespace(statistics=DashboardStatistics(), stopped=False,
                               decision_trace=_trace(history, [.1] * 5, strategy.predictor.model_id))
    monkeypatch.setattr(service, "_run_strategy", replay)
    repos.model_registry.get = lambda _: candidate
    monkeypatch.setattr("app.backtest.backtest_service.RepositoryFactory", lambda: repos)
    request = SimpleNamespace(strategy_id=2, candidate_model_id="a", symbol="XAUUSD", timeframe="M5", initial_balance=10000)
    response = service._run_candidate_comparison(request, history, None)
    saved = json.loads(candidate.metadata_json)["review_history"][-1]["evidence"]
    assert saved["candidate"]["net_profit"] == 0
    assert saved["prediction_quality"]["samples"] == 4
    assert saved["provenance"]["champion_sha256"] == "b" * 64
    assert response.comparison["history_saved"] is True
    assert response.decision_trace is None
    assert candidate.status == "candidate"
    def fail(*args):
        raise RuntimeError("database unavailable")
    repos.model_registry.add_review_event = fail
    response = service._run_candidate_comparison(request, history, None)
    assert response.comparison["history_saved"] is False


def test_cancelled_champion_does_not_save_completed_comparison(monkeypatch):
    service = BacktestService()
    history = _history()
    models = [SimpleNamespace(model_id="a"), SimpleNamespace(model_id="b")]
    monkeypatch.setattr(service, "_load_strategy_definition", lambda _: ("AI_ASSISTED_XGB", {}))
    monkeypatch.setattr(service, "_comparison_models", lambda *args: (*models, history.index[0]))
    reports = iter([SimpleNamespace(stopped=False, decision_trace=[]), SimpleNamespace(stopped=True, decision_trace=[])])
    monkeypatch.setattr(service, "_run_strategy", lambda *args, **kwargs: next(reports))
    monkeypatch.setattr(service, "_record_candidate_review", lambda *args: pytest.fail("must not save incomplete comparison"))
    result = service._run_candidate_comparison(SimpleNamespace(strategy_id=2, candidate_model_id="a", symbol="XAUUSD", timeframe="M5"), history, None)
    assert result.stopped
    assert result.comparison["status"] == "stopped"


def test_comparison_starts_after_both_model_training_windows(monkeypatch):
    from tests.test_candidate_comparison import _model
    def metadata(start):
        return json.dumps({"market_context": {"symbol": "XAUUSD", "timeframe": "M5"}, "evaluation_window": {"start_time": start}})
    candidate = _model("a", "candidate", metadata("2026-01-01T00:00:00+00:00"))
    champion = _model("b", "champion", metadata("2026-01-02T00:00:00+00:00"))
    repos = SimpleNamespace(model_registry=SimpleNamespace(get=lambda _: candidate, get_champion=lambda *args: champion), close=lambda: None)
    monkeypatch.setattr("app.backtest.backtest_service.RepositoryFactory", lambda: repos)
    _, _, start = BacktestService()._comparison_models("a", "XAUUSD", "M5", {})
    assert start == pd.Timestamp("2026-01-02T00:00:00+00:00")


def test_real_paper_replays_explain_identical_trades_with_different_predictions(monkeypatch):
    from app.ml.inference import Prediction
    history = pd.DataFrame({"Open": [100 + i * .2 for i in range(85)],
                            "High": [101 + i * .2 for i in range(85)],
                            "Low": [99 + i * .2 for i in range(85)],
                            "Close": [100 + i * .2 for i in range(85)], "Volume": 10},
                           index=pd.date_range("2026-01-01", periods=85, freq="5min", tz="UTC"))
    def features(df):
        return pd.DataFrame([{"ema_20": 100, "ema_50": 101, "adx_14": 30,
                              "atr_percent": .001, "rsi_14": 40, "atr_14": 1,
                              "plus_di_14": 15, "minus_di_14": 30}], index=df.index[-1:])
    monkeypatch.setattr("app.strategy.ai_assisted_xgb.build_core_v1_features", features)
    monkeypatch.setattr("app.ml.inference.RegisteredModelPredictor.predict",
                        lambda self, *args, **kwargs: Prediction(self.model_id, .1 if self.model_id == "a" else .2, .75, .15 if self.model_id == "a" else .05))
    service = BacktestService()
    candidate = SimpleNamespace(model_id="a", artifact_sha256="a" * 64,
                                metadata_json=json.dumps({"prediction_baseline": {"positive_rate": .3}}))
    champion = SimpleNamespace(model_id="b", artifact_sha256="b" * 64)
    monkeypatch.setattr(service, "_comparison_models", lambda *args: (candidate, champion, history.index[0]))
    monkeypatch.setattr(service, "_load_strategy_definition", lambda _: ("AI_ASSISTED_XGB", {"horizon_candles": 1, "up_return_threshold": .001}))
    saved = []
    monkeypatch.setattr(service, "_record_candidate_review", lambda _, report: saved.append(json.dumps(report, allow_nan=False)) or True)
    request = SimpleNamespace(strategy_id=2, candidate_model_id="a", symbol="XAUUSD", timeframe="M5", bars=85, initial_balance=10000)
    comparison = service._run_candidate_comparison(request, history, None).comparison
    assert comparison["candidate"] == comparison["champion"]
    assert comparison["candidate"]["total_trades"] > 0
    assert comparison["decision_diagnostic"]["decision_disagreements"] == 0
    assert comparison["prediction_quality"]["samples"] == 24
    assert comparison["prediction_quality"]["candidate"]["brier_score"] != comparison["prediction_quality"]["champion"]["brier_score"]
    outcomes = comparison["filter_diagnostics"]["candidate"]["execution_outcomes"]
    assert outcomes["Submitted to broker"] > 0
    assert outcomes["Position already exists for XAUUSD"] > 0
    assert len(saved) == 1
