"""An OpenAI-backed, paper-trading signal strategy.

The model is deliberately limited to choosing BUY, SELL, or HOLD.  Position
sizing remains in ``RiskManager`` and stop-loss / take-profit levels are
calculated locally, so an API response cannot bypass the application's risk
controls.
"""

import json
import logging
import math
import os
from typing import Optional

import pandas as pd
import requests

from app.config import TradingConfig
from app.enums.signal_action import SignalAction
from app.models.signal import TradingSignal
from app.strategy.base import Strategy
from app.strategy.parameter import StrategyParameter


logger = logging.getLogger(__name__)


class AIAgentStrategy(Strategy):
    """Ask the Responses API for a constrained market-direction signal."""

    RESPONSE_SCHEMA = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
        },
        "required": ["action", "confidence", "reason"],
    }

    @classmethod
    def schema(cls) -> list[StrategyParameter]:
        return [
            StrategyParameter(
                key="lookback_bars", label="Candles supplied to AI",
                type="number", default=30, minimum=10, maximum=100, step=1,
            ),
            StrategyParameter(
                key="min_confidence", label="Minimum AI confidence",
                type="number", default=0.65, minimum=0, maximum=1, step=0.05,
            ),
            StrategyParameter(
                key="stop_loss_pips", label="Stop Loss (Pips)",
                type="number", default=300, minimum=10, maximum=5000, step=10,
            ),
            StrategyParameter(
                key="risk_reward_ratio", label="Risk Reward Ratio",
                type="number", default=2.0, minimum=0.5, maximum=10, step=0.1,
            ),
            StrategyParameter(
                key="backtest_stride", label="Backtest AI evaluation interval",
                type="number", default=20, minimum=1, maximum=200, step=1,
            ),
        ]

    def __init__(self, config: dict):
        self.lookback_bars = int(config.get("lookback_bars", 30))
        self.min_confidence = float(config.get("min_confidence", 0.65))
        self.stop_loss_pips = float(config.get("stop_loss_pips", 300))
        self.risk_reward_ratio = float(config.get("risk_reward_ratio", 2.0))
        self.backtest_stride = max(1, int(config.get("backtest_stride", 20)))
        self.model = os.environ.get("OPENAI_TRADING_MODEL", "gpt-5-mini")
        self.api_key = (
            os.environ.get("AI_API_KEY")
            or os.environ.get("OMNIROUTE_API_KEY")
            or os.environ.get("OPENAI_API_KEY", "")
        )
        self.api_base_url = os.environ.get(
            "AI_API_BASE_URL", "https://api.openai.com/v1"
        ).rstrip("/")
        self.timeout_seconds = float(os.environ.get("OPENAI_TRADING_TIMEOUT_SECONDS", "20"))
        self._backtest_evaluation_count: Optional[int] = None

    @property
    def name(self) -> str:
        return "AI Agent"

    @property
    def minimum_bars(self) -> int:
        return self.lookback_bars

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.copy()

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> Optional[TradingSignal]:
        last = df.iloc[-1]
        price = float(last["Close"])
        timestamp = df.index[-1]

        if not self._should_evaluate_backtest_candle():
            return self._hold(
                symbol,
                price,
                timestamp,
                f"AI skipped for backtest interval ({self.backtest_stride} candles)",
            )

        if not self.api_key:
            return self._hold(symbol, price, timestamp, "No AI gateway API key is configured")

        try:
            decision = self._request_decision(symbol, df)
            action = SignalAction(decision["action"])
            confidence = max(0.0, min(1.0, float(decision["confidence"])))
            reason = str(decision["reason"]).strip()[:255]
        except (KeyError, TypeError, ValueError, requests.RequestException, json.JSONDecodeError) as exc:
            logger.warning("AI signal request failed; returning HOLD: %s", exc)
            return self._hold(symbol, price, timestamp, "AI decision unavailable")

        if action != SignalAction.HOLD and confidence < self.min_confidence:
            return self._hold(
                symbol, price, timestamp,
                f"AI confidence {confidence:.2f} below minimum {self.min_confidence:.2f}",
                confidence,
            )

        stop_loss, take_profit = self._levels(action, price)
        return TradingSignal(
            symbol=symbol,
            action=action,
            price=price,
            time=timestamp,
            reason=reason or "AI agent decision",
            confidence=confidence,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def start_backtest(self) -> None:
        """Evaluate AI only periodically while a backtest replays each candle."""
        self._backtest_evaluation_count = 0

    def end_backtest(self) -> None:
        self._backtest_evaluation_count = None

    def _should_evaluate_backtest_candle(self) -> bool:
        if self._backtest_evaluation_count is None:
            return True

        count = self._backtest_evaluation_count
        self._backtest_evaluation_count += 1
        return count % self.backtest_stride == 0

    def _request_decision(self, symbol: str, df: pd.DataFrame) -> dict:
        candles = []
        for time, row in df.tail(self.lookback_bars).iterrows():
            candles.append({
                "time": str(time),
                "open": self._number(row["Open"]),
                "high": self._number(row["High"]),
                "low": self._number(row["Low"]),
                "close": self._number(row["Close"]),
                "volume": self._number(row["Volume"]),
            })

        payload = {
            "model": self.model,
            "store": False,
            "instructions": (
                "You are a cautious paper-trading signal analyst. Analyze only the supplied "
                "OHLCV candles. Return BUY or SELL only for a clear, high-confidence setup; "
                "otherwise return HOLD. Do not suggest position size or risk levels."
            ),
            "input": json.dumps({"symbol": symbol, "candles": candles}),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "trading_signal",
                    "strict": True,
                    "schema": self.RESPONSE_SCHEMA,
                }
            },
        }
        response = requests.post(
            f"{self.api_base_url}/responses",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return json.loads(self._response_text(response.json()))

    @staticmethod
    def _response_text(response: dict) -> str:
        """Extract generated text from the raw Responses API JSON payload."""
        # ``output_text`` is a convenience property in official SDKs. The raw
        # HTTP response contains its text in one or more output message items.
        if response.get("output_text"):
            return response["output_text"]

        texts = []
        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    texts.append(content.get("text", ""))
        if not texts:
            raise ValueError("Responses API returned no output text")
        return "".join(texts)

    def _levels(self, action: SignalAction, price: float) -> tuple[Optional[float], Optional[float]]:
        if action == SignalAction.HOLD:
            return None, None
        stop_distance = self.stop_loss_pips * TradingConfig.PIP_SIZE
        take_distance = stop_distance * self.risk_reward_ratio
        if action == SignalAction.BUY:
            return price - stop_distance, price + take_distance
        return price + stop_distance, price - take_distance

    @staticmethod
    def _number(value) -> Optional[float]:
        number = float(value)
        return number if math.isfinite(number) else None

    @staticmethod
    def _hold(symbol, price, timestamp, reason, confidence=0.0) -> TradingSignal:
        return TradingSignal(
            symbol=symbol, action=SignalAction.HOLD, price=price, time=timestamp,
            reason=reason, confidence=confidence,
        )
