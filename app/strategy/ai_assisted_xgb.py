"""Optional paper-only strategy that combines champion probabilities and rules."""

from uuid import uuid4
import math

from app.features.core_v1 import FEATURE_SET_ID, build_core_v1_features
from app.features.raw_ohlcv_v1 import FEATURE_SET_ID as RAW_FEATURE_SET_ID, LOOKBACK_CANDLES, build_raw_ohlcv_features
from app.config import TradingConfig
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
        # Preserve existing configurations: a 0.30 short cutoff now requires
        # at least 0.70 probability of an actual downward return event.
        self.down_probability_threshold = float(config.get("down_probability_threshold", 1.0 - self.short_probability_threshold))
        self.feature_set_id = config.get("feature_set_id", FEATURE_SET_ID)
        if self.feature_set_id not in {FEATURE_SET_ID, RAW_FEATURE_SET_ID}:
            raise ValueError(f"unsupported feature set: {self.feature_set_id}")
        self.use_technical_filters = config.get("use_technical_filters", self.feature_set_id != RAW_FEATURE_SET_ID)
        if not isinstance(self.use_technical_filters, bool):
            raise ValueError("use_technical_filters must be a boolean")
        if self.feature_set_id == RAW_FEATURE_SET_ID and self.use_technical_filters:
            raise ValueError("raw price/volume models require technical entry filters to be off")
        self.model_stop_loss_percent = float(config.get("model_stop_loss_percent", 0.5))
        if not math.isfinite(self.model_stop_loss_percent) or not 0 < self.model_stop_loss_percent < 100:
            raise ValueError("model_stop_loss_percent must be between zero and 100")
        if not (0 <= self.short_probability_threshold < self.long_probability_threshold <= 1):
            raise ValueError("probability thresholds must be between zero and one, with short below long")
        if not math.isfinite(self.down_probability_threshold) or not 0.5 <= self.down_probability_threshold <= 1:
            raise ValueError("down probability threshold must be between 0.5 and one")
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
        self.timeframe = str(config.get("timeframe", TradingConfig.TIMEFRAME))

    @property
    def name(self):
        return "AI Assisted XGBoost (Paper Only)"

    @classmethod
    def schema(cls):
        return [
            StrategyParameter(key="feature_set_id", label="Model inputs", type="select", default=FEATURE_SET_ID, options=[{"value": FEATURE_SET_ID, "label": "Price, volume and technical indicators"}, {"value": RAW_FEATURE_SET_ID, "label": "Raw price and volume only"}], description="Must match the model's training inputs. Raw price/volume uses the last 12 completed candles without technical indicators. Learning occurs during training and retraining."),
            StrategyParameter(key="use_technical_filters", label="Use ADX, RSI and trend entry filters", type="boolean", default=True, description="Turn off for entries based only on model probability thresholds. Raw price/volume models always run with these filters off."),
            StrategyParameter(key="horizon_candles", label="Label horizon candles", type="number", default=12, minimum=1, maximum=100, step=1),
            StrategyParameter(key="up_return_threshold", label="Return target (up and down)", type="number", default=0.003, minimum=0.00001, maximum=1, step=0.00001, description="Train UP for a rise of at least this fraction and DOWN for an equal-sized fall. Smaller moves are neutral. 0.003 means 0.3%."),
            StrategyParameter(key="long_probability_threshold", label="Long probability", type="number", default=0.70, minimum=0.5, maximum=1, step=0.01),
            StrategyParameter(key="down_probability_threshold", label="SELL probability of a fall", type="number", default=0.70, minimum=0.5, maximum=1, step=0.01, description="SELL requires a learned downward-event probability at or above this threshold. Retrain legacy UP-only models to enable SELL."),
            StrategyParameter(key="adx_threshold", label="ADX threshold", type="number", default=25, minimum=1, maximum=100, step=1),
            StrategyParameter(key="stop_atr_multiple", label="Stop ATR multiple", type="number", default=1.5, minimum=0.1, maximum=10, step=0.1),
            StrategyParameter(key="model_stop_loss_percent", label="Stop loss (%) when technical filters are off", type="number", default=0.5, minimum=0.01, maximum=99, step=0.01, description="Fixed percentage of entry price; replaces the ATR stop in model probability mode. Position sizing and risk limits still apply."),
            StrategyParameter(key="reward_risk_ratio", label="Reward/risk ratio", type="number", default=2, minimum=0.1, maximum=10, step=0.1),
        ]

    @property
    def minimum_bars(self):
        return LOOKBACK_CANDLES if self.feature_set_id == RAW_FEATURE_SET_ID else 60

    def prepare(self, df):
        # Feature calculation happens in generate_signal so this strategy never
        # leaks a feature or label column into the shared source dataframe.
        return df.copy()

    def generate_signal(self, symbol, df):
        price = float(df.iloc[-1]["Close"])
        timestamp = df.index[-1]
        gates = {"data_fresh": True, "champion_available": False, "technical_filters_enabled": self.use_technical_filters}
        reasons = []
        try:
            features = build_raw_ohlcv_features(df) if self.feature_set_id == RAW_FEATURE_SET_ID else build_core_v1_features(df)
            latest = features.iloc[-1]
        except (ValueError, IndexError) as error:
            return self._hold(symbol, price, timestamp, gates, [f"feature validation failed: {error}"])

        regime = self.regimes.classify(latest) if self.use_technical_filters else None
        regime_name = regime.regime if regime else "model_probability"
        regime_reasons = regime.reasons if regime else []
        label = FutureReturnLabel(self.horizon_candles, self.up_return_threshold)
        try:
            prediction = self.predictor.predict(
                latest.to_frame().T,
                self.feature_set_id,
                label.definition_id,
                symbol=symbol,
                timeframe=self.timeframe,
            )
            gates["champion_available"] = True
        except ChampionUnavailable as error:
            return self._hold(symbol, price, timestamp, gates, regime_reasons + [str(error)], regime_name)

        probability = prediction.probability_up
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            return self._hold(symbol, price, timestamp, gates, ["model returned an invalid probability"], regime_name)
        down_probability = prediction.probability_down
        neutral_probability = prediction.probability_neutral
        if down_probability is None and neutral_probability is not None:
            return self._hold(symbol, price, timestamp, gates, ["model returned incomplete directional probabilities"], regime_name)
        if down_probability is not None:
            if not math.isfinite(down_probability) or not 0 <= down_probability <= 1 or probability + down_probability > 1 + 1e-9:
                return self._hold(symbol, price, timestamp, gates, ["model returned invalid directional probabilities"], regime_name)
            if neutral_probability is None:
                neutral_probability = max(0.0, 1.0 - probability - down_probability)
            if not math.isfinite(neutral_probability) or not 0 <= neutral_probability <= 1 or abs(probability + down_probability + neutral_probability - 1) > 1e-9:
                return self._hold(symbol, price, timestamp, gates, ["model returned invalid directional probabilities"], regime_name)
        gates.update({
            "long_probability": bool(probability >= self.long_probability_threshold),
            "downside_model_available": down_probability is not None,
            "short_probability": bool(down_probability is not None and down_probability >= self.down_probability_threshold and down_probability > probability and down_probability > neutral_probability),
        })
        if neutral_probability is not None:
            gates["long_probability"] = bool(gates["long_probability"] and probability > neutral_probability and probability > down_probability)
        if self.use_technical_filters:
            gates.update({
                "adx": bool(latest["adx_14"] >= self.adx_threshold),
                "long_rsi": bool(self.rsi_long_min <= latest["rsi_14"] <= self.rsi_long_max),
                "short_rsi": bool(self.rsi_short_min <= latest["rsi_14"] <= self.rsi_short_max),
                "trend_up": regime_name == "trend_up",
                "trend_down": regime_name == "trend_down",
            })
        action = SignalAction.HOLD
        long_gates = ("adx", "long_probability", "long_rsi", "trend_up") if self.use_technical_filters else ("long_probability",)
        short_gates = ("adx", "short_probability", "short_rsi", "trend_down") if self.use_technical_filters else ("short_probability",)
        if all(gates[key] for key in long_gates):
            action = SignalAction.BUY
            reasons.append("model probability and long technical/regime gates passed" if self.use_technical_filters else "model long probability threshold passed; technical entry filters disabled")
        elif all(gates[key] for key in short_gates):
            action = SignalAction.SELL
            reasons.append("downward-event probability and short technical/regime gates passed" if self.use_technical_filters else "model downward-event probability threshold passed; technical entry filters disabled")
        else:
            reasons.append("one or more probability, technical, or regime gates did not pass" if self.use_technical_filters else "neither directional probability passed its entry threshold")
        if down_probability is None:
            reasons.append("legacy UP-only model: retrain and review a directional candidate to enable SELL")
        stop_distance = float(latest["atr_14"] * self.stop_atr_multiple) if self.use_technical_filters else price * self.model_stop_loss_percent / 100
        stop_loss, take_profit = self._risk_levels(action, price, stop_distance)
        signal = TradingSignal(
            symbol=symbol, action=action, price=price, time=timestamp,
            confidence=down_probability if action == SignalAction.SELL else neutral_probability if action == SignalAction.HOLD and neutral_probability is not None else probability,
            reason="; ".join(regime_reasons + reasons),
            ema=float(latest["ema_20"]) if "ema_20" in latest else None,
            rsi=float(latest["rsi_14"]) if "rsi_14" in latest else None,
            adx=float(latest["adx_14"]) if "adx_14" in latest else None,
            plus_di=float(latest["plus_di_14"]) if "plus_di_14" in latest else None,
            minus_di=float(latest["minus_di_14"]) if "minus_di_14" in latest else None,
            stop_loss=stop_loss, take_profit=take_profit,
        )
        signal.ai_lab_context = {
            "decision_id": uuid4().hex,
            "model_id": prediction.model_id,
            "probability_up": probability,
            "probability_down": down_probability,
            "probability_neutral": neutral_probability,
            "regime": regime_name,
            "gates": gates,
            "reasons": regime_reasons + reasons,
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
