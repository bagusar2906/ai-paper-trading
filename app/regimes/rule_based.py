from dataclasses import dataclass


@dataclass(frozen=True)
class RegimeDecision:
    regime: str
    reasons: list[str]


class RuleBasedRegimeClassifier:
    """Explainable regime classifier based solely on the current feature row."""

    def __init__(self, adx_threshold: float = 25.0, high_volatility_atr_percent: float = 0.01):
        self.adx_threshold = adx_threshold
        self.high_volatility_atr_percent = high_volatility_atr_percent

    def classify(self, features) -> RegimeDecision:
        if features is None or features.isna().any():
            return RegimeDecision("unknown", ["features are missing or incomplete"])
        if features["atr_percent"] >= self.high_volatility_atr_percent:
            return RegimeDecision("high_volatility", ["ATR percent exceeds configured threshold"])
        if features["adx_14"] < self.adx_threshold:
            return RegimeDecision("range", ["ADX is below configured trend threshold"])
        if features["ema_20"] > features["ema_50"]:
            return RegimeDecision("trend_up", ["EMA20 is above EMA50 and ADX is strong"])
        if features["ema_20"] < features["ema_50"]:
            return RegimeDecision("trend_down", ["EMA20 is below EMA50 and ADX is strong"])
        return RegimeDecision("unknown", ["trend direction is indeterminate"])
