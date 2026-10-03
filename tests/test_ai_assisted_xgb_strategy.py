from datetime import datetime, timezone

import pandas as pd

from app.brokers.paper_broker import PaperBroker
from app.engine.trading_engine import TradingEngine
from app.enums.signal_action import SignalAction
from app.ml.inference import ChampionUnavailable, Prediction
from app.models.signal import TradingSignal
from app.regimes import RuleBasedRegimeClassifier
from app.strategy.ai_assisted_xgb import AIAssistedXGBStrategy


def _features():
    return pd.DataFrame([{
        "ema_20": 101.0, "ema_50": 100.0, "adx_14": 30.0,
        "atr_percent": 0.002, "rsi_14": 60.0, "atr_14": 2.0,
        "plus_di_14": 30.0, "minus_di_14": 15.0,
    }], index=pd.DatetimeIndex([datetime(2026, 1, 1, tzinfo=timezone.utc)]))


def _candles():
    return pd.DataFrame({
        "Open": [100.0], "High": [101.0], "Low": [99.0],
        "Close": [100.5], "Volume": [10.0],
    }, index=pd.DatetimeIndex([datetime(2026, 1, 1, tzinfo=timezone.utc)]))


class _Predictor:
    def predict(self, features, feature_set_id, label_definition_id):
        return Prediction("champion-xgb-v1", 0.8)


class _UnavailablePredictor:
    def predict(self, features, feature_set_id, label_definition_id):
        raise ChampionUnavailable("no promoted champion model is available")


def test_rule_based_regime_is_explainable():
    decision = RuleBasedRegimeClassifier().classify(_features().iloc[0])
    assert decision.regime == "trend_up"
    assert decision.reasons


def test_ai_assisted_schema_is_serializable_for_the_strategy_editor():
    assert [field.key for field in AIAssistedXGBStrategy.schema()] == [
        "horizon_candles", "up_return_threshold", "long_probability_threshold",
        "short_probability_threshold", "adx_threshold", "stop_atr_multiple",
        "reward_risk_ratio",
    ]


def test_ai_assisted_strategy_requires_a_champion(monkeypatch):
    monkeypatch.setattr("app.strategy.ai_assisted_xgb.build_core_v1_features", lambda df: _features())
    signal = AIAssistedXGBStrategy(predictor=_UnavailablePredictor()).generate_signal("XAUUSD", _candles())
    assert signal.action == SignalAction.HOLD
    assert signal.ai_lab_context["gates"]["champion_available"] is False


def test_ai_assisted_strategy_combines_probability_regime_and_technical_gates(monkeypatch):
    monkeypatch.setattr("app.strategy.ai_assisted_xgb.build_core_v1_features", lambda df: _features())
    signal = AIAssistedXGBStrategy(predictor=_Predictor()).generate_signal("XAUUSD", _candles())
    assert signal.action == SignalAction.BUY
    assert signal.ai_lab_context["model_id"] == "champion-xgb-v1"
    assert signal.ai_lab_context["regime"] == "trend_up"
    assert signal.stop_loss < signal.price < signal.take_profit


def test_ai_assisted_decision_is_journaled_after_risk_rejection(repos):
    broker = PaperBroker(repos=repos)
    engine = TradingEngine(None, None, broker, "XAUUSD", "M5", respect_trading_mode=False)
    signal = TradingSignal(
        symbol="XAUUSD", action=SignalAction.HOLD, price=100.0,
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    signal.ai_lab_context = {
        "decision_id": "decision-risk-rejected",
        "model_id": "champion-xgb-v1",
        "regime": "range",
        "gates": {"champion_available": True, "probability": False},
        "reasons": ["probability gate did not pass"],
    }
    engine._execute_signal(signal)
    entry = repos.decision_journal.get_by_decision_id("decision-risk-rejected")
    assert entry.risk_status == "rejected"
    assert entry.paper_only is True
