import json

import pandas as pd

from app.enums.signal_action import SignalAction
from app.strategy.ai_agent import AIAgentStrategy


def _candles(count=30):
    index = pd.date_range("2026-01-01", periods=count, freq="5min")
    return pd.DataFrame({
        "Open": [2000.0] * count,
        "High": [2001.0] * count,
        "Low": [1999.0] * count,
        "Close": [2000.0] * count,
        "Volume": [500.0] * count,
    }, index=index)


def test_ai_strategy_returns_buy_and_local_risk_levels(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"output": [{"type": "message", "content": [{
                "type": "output_text",
                "text": json.dumps({"action": "BUY", "confidence": 0.9, "reason": "Momentum breakout"}),
            }]}]}

    captured = {}

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("app.strategy.ai_agent.requests.post", fake_post)
    strategy = AIAgentStrategy({"lookback_bars": 10, "min_confidence": 0.7, "stop_loss_pips": 50, "risk_reward_ratio": 2})

    signal = strategy.generate_signal("XAUUSD", _candles())

    assert signal.action == SignalAction.BUY
    assert signal.stop_loss == 1995.0
    assert signal.take_profit == 2010.0
    assert captured["json"]["store"] is False
    assert len(json.loads(captured["json"]["input"])["candles"]) == 10


def test_ai_strategy_holds_without_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    signal = AIAgentStrategy({}).generate_signal("XAUUSD", _candles())

    assert signal.action == SignalAction.HOLD
    assert "API key" in signal.reason


def test_ai_strategy_schema_is_serializable_for_the_editor():
    schema = AIAgentStrategy.schema()

    assert [field.key for field in schema] == [
        "lookback_bars",
        "min_confidence",
        "stop_loss_pips",
        "risk_reward_ratio",
        "backtest_stride",
    ]


def test_ai_strategy_reduces_backtest_api_calls(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"output_text": '{"action":"HOLD","confidence":0.5,"reason":"wait"}'}

    calls = []
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.strategy.ai_agent.requests.post",
        lambda *args, **kwargs: (calls.append(1) or Response()),
    )
    strategy = AIAgentStrategy({"backtest_stride": 3})
    strategy.start_backtest()

    for _ in range(5):
        strategy.generate_signal("XAUUSD", _candles())

    strategy.end_backtest()
    assert len(calls) == 2


def test_ai_strategy_uses_configured_gateway_url(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"output_text": '{"action":"HOLD","confidence":0.5,"reason":"wait"}'}

    called = {}
    monkeypatch.setenv("OMNIROUTE_API_KEY", "gateway-key")
    monkeypatch.setenv("AI_API_BASE_URL", "http://localhost:20128/v1/")
    monkeypatch.setattr(
        "app.strategy.ai_agent.requests.post",
        lambda url, **kwargs: (called.update(url=url) or Response()),
    )

    AIAgentStrategy({}).generate_signal("XAUUSD", _candles())

    assert called["url"] == "http://localhost:20128/v1/responses"


def test_ai_strategy_rejects_low_confidence(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"output_text": '{"action":"SELL","confidence":0.4,"reason":"weak"}'}

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("app.strategy.ai_agent.requests.post", lambda *args, **kwargs: Response())
    signal = AIAgentStrategy({"min_confidence": 0.65}).generate_signal("XAUUSD", _candles())

    assert signal.action == SignalAction.HOLD
