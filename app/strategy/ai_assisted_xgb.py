"""Optional paper-only strategy that combines champion probabilities and rules."""

from uuid import uuid4

from app.features.core_v1 import FEATURE_SET_ID, build_core_v1_features
from app.labels.future_return import FutureReturnLabel
from app.ml.inference import ChampionModelPredictor, ChampionUnavailable
from app.models.signal import TradingSignal
from app.enums.signal_action import SignalAction
from app.regimes import RuleBasedRegimeClassifier
from app.strategy.base import Strategy
from app.strategy.parameter import StrategyParameter


class AIAssistedXGBStrategy(Strategy):
    """A candidate model cannot reach this strategy's execution output."""

    def __init__(self, config=None, predictor=None):
        config = config or {}
        self.horizon_candles = int(config.get("horizon_candles", 12))
        self.up_return_threshold = float(config.get("up_return_threshold", 0.003))
        self.long_probability_threshold = float(config.get("long_probability_threshold", 0.70))
        self.short_probability_threshold = float(config.get("short_probability_threshold", 0.30))
        self.adx_threshold = float(config.get("adx_threshold", 25))
        self.rsi_long_min = float(config.get("rsi_long_min", 50))
        self.rsi_long_max = float(config.get("rsi_long_max", 70))
        self.rsi_short_min = float(config.get("rsi_short_min", 30))
        self.rsi_short_max = float(config.get("rsi_short_max", 50))
        self.stop_atr_multiple = float(config.get("stop_atr_multiple", 1.5))
        self.reward_risk_ratio = float(config.get("reward_risk_ratio", 2.0))
        self.regimes = RuleBasedRegimeClassifier(
            adx_threshold=self.adx_threshold,
            high_volatility_atr_percent=float(config.get("high_volatility_atr_percent", 0.01)),
        )
        self.predictor = predictor or ChampionModelPredictor()

    @property
    def name(self):
        return "AI Assisted XGBoost (Paper Only)"

    @classmethod
    def schema(cls):
        return [
            StrategyParameter("horizon_candles", "Label horizon candles", "number", 12, 1, 100, 1),
            StrategyParameter("up_return_threshold", "Up-return threshold", "number", 0.003, 0.00001, 1, 0.00001),
            StrategyParameter("long_probability_threshold", "Long probability", "number", 0.70, 0.5, 1, 0.01),
            StrategyParameter("short_probability_threshold", "Short probability", "number", 0.30, 0, 0.5, 0.01),
            StrategyParameter("adx_threshold", "ADX threshold", "number", 25, 1, 100, 1),
            StrategyParameter("stop_atr_multiple", "Stop ATR multiple", "number", 1.5, 0.1, 10, 0.1),
            StrategyParameter("reward_risk_ratio", "Reward/risk ratio", "number", 2, 0.1, 10, 0.1),
        ]

    @property
    def minimum_bars(self):
        return 60

    def prepare(self, df):
        # Feature calculation happens in generate_signal so this strategy never
        # leaks a feature or label column into the shared source dataframe.
        return df.copy()

    def generate_signal(self, symbol, df):
        price = float(df.iloc[-1]["Close"])
        timestamp = df.index[-1]
        gates = {"data_fresh": True, "champion_available": False}
        reasons = []
        try:
            features = build_core_v1_features(df)
            latest = features.iloc[-1]
        except (ValueError, IndexError) as error:
            return self._hold(symbol, price, timestamp, gates, [f"feature validation failed: {error}"])

        regime = self.regimes.classify(latest)
        label = FutureReturnLabel(self.horizon_candles, self.up_return_threshold)
        try:
            prediction = self.predictor.predict(
                latest.to_frame().T,
                FEATURE_SET_ID,
                label.definition_id,
            )
            gates["champion_available"] = True
        except ChampionUnavailable as error:
            return self._hold(symbol, price, timestamp, gates, regime.reasons + [str(error)], regime.regime)

        probability = prediction.probability_up
        gates.update({
            "adx": bool(latest["adx_14"] >= self.adx_threshold),
            "long_probability": bool(probability >= self.long_probability_threshold),
            "short_probability": bool(probability <= self.short_probability_threshold),
            "long_rsi": bool(self.rsi_long_min <= latest["rsi_14"] <= self.rsi_long_max),
            "short_rsi": bool(self.rsi_short_min <= latest["rsi_14"] <= self.rsi_short_max),
            "trend_up": regime.regime == "trend_up",
            "trend_down": regime.regime == "trend_down",
        })
        action = SignalAction.HOLD
        if all(gates[key] for key in ("adx", "long_probability", "long_rsi", "trend_up")):
            action = SignalAction.BUY
            reasons.append("champion probability and long technical/regime gates passed")
        elif all(gates[key] for key in ("adx", "short_probability", "short_rsi", "trend_down")):
            action = SignalAction.SELL
            reasons.append("champion probability and short technical/regime gates passed")
        else:
            reasons.append("one or more probability, technical, or regime gates did not pass")
        stop_distance = float(latest["atr_14"] * self.stop_atr_multiple)
        stop_loss, take_profit = self._risk_levels(action, price, stop_distance)
        signal = TradingSignal(
            symbol=symbol, action=action, price=price, time=timestamp,
            confidence=probability, reason="; ".join(regime.reasons + reasons),
            ema=float(latest["ema_20"]), rsi=float(latest["rsi_14"]), adx=float(latest["adx_14"]),
            plus_di=float(latest["plus_di_14"]), minus_di=float(latest["minus_di_14"]),
            stop_loss=stop_loss, take_profit=take_profit,
        )
        signal.ai_lab_context = {
            "decision_id": uuid4().hex,
            "model_id": prediction.model_id,
            "regime": regime.regime,
            "gates": gates,
            "reasons": regime.reasons + reasons,
        }
        return signal

    def _hold(self, symbol, price, timestamp, gates, reasons, regime="unknown"):
        signal = TradingSignal(
            symbol=symbol, action=SignalAction.HOLD, price=price, time=timestamp,
            confidence=0.0, reason="; ".join(reasons),
        )
        signal.ai_lab_context = {
            "decision_id": uuid4().hex,
            "model_id": None,
            "regime": regime,
            "gates": gates,
            "reasons": reasons,
        }
        return signal

    def _risk_levels(self, action, price, stop_distance):
        if action == SignalAction.BUY:
            return price - stop_distance, price + stop_distance * self.reward_risk_ratio
        if action == SignalAction.SELL:
            return price + stop_distance, price - stop_distance * self.reward_risk_ratio
        return None, None
