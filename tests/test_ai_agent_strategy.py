import json
from types import SimpleNamespace

import pandas as pd
import pytest

from app.engine.trading_engine import TradingEngine
from app.enums.signal_action import SignalAction
from app.enums.trading_mode import TradingMode
from app.models.signal import TradingSignal
from app.strategy.ai_agent import AIAgentStrategy
from app.strategy.sol_agent.agents import Decision


def candles(count=241, freq="h", tz=None):
    index = pd.date_range("2026-01-01", periods=count, freq=freq, tz=tz)
    return pd.DataFrame({"Open": 2000., "High": 2001., "Low": 1999.,
                         "Close": 2000., "Volume": 500.}, index=index)


@pytest.fixture
def strategy(monkeypatch, tmp_path, broker):
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_TRADING_MODEL", raising=False)
    result = AIAgentStrategy({"decision_every_n_bars": 1})
    result.cfg["CACHE_DIR"] = str(tmp_path / "cache")
    result.bind_broker(broker)
    return result


def response(monkeypatch, action="buy", status="completed", arguments=None, multiple=False):
    captured = []
    order = {"type": "function_call", "name": "place_order", "call_id": "order",
             "arguments": arguments if arguments is not None else json.dumps({
                 "action": action, "sl_atr": 2, "tp_atr": 4, "reason": "Momentum setup"})}
    data = {"status": status, "output": [order, order] if multiple else [order],
            "usage": {"input_tokens": 20, "output_tokens": 10}}

    def post(url, **kwargs):
        captured.append({"url": url, **kwargs})
        return SimpleNamespace(text=json.dumps(data), raise_for_status=lambda: None)

    monkeypatch.setattr("app.strategy.ai_agent.requests.post", post)
    return captured


def engine(strategy, broker, auto=True):
    broker.repos.settings.set("trading_mode", (TradingMode.AUTO if auto else TradingMode.MANUAL).value)
    return TradingEngine(None, strategy, broker, "XAUUSD", "M5", respect_trading_mode=True)


def test_replacement_requests_source_agent_tool_and_atr_levels(strategy, monkeypatch):
    captured = response(monkeypatch)
    signal = strategy.generate_signal("XAUUSD", candles())
    assert signal.action == SignalAction.BUY
    assert signal.stop_loss == 1996
    assert signal.take_profit == 2008
    payload = captured[0]["json"]
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["reasoning"] == {"effort": "medium"}
    assert payload["tool_choice"] == {"type": "function", "name": "place_order"}
    assert payload["store"] is False
    assert payload["parallel_tool_calls"] is False
    snapshot = payload["input"][0]["content"]
    assert "1H price context" in snapshot and "1D price context" in snapshot
    assert "Asset X" in snapshot and "XAUUSD" not in snapshot


def test_missing_credentials_holds(strategy):
    strategy.client.api_key = ""
    signal = strategy.generate_signal("XAUUSD", candles())
    assert signal.action == SignalAction.HOLD and "API key" in signal.reason


@pytest.mark.parametrize("kwargs", [
    {"status": "incomplete"}, {"status": "failed"}, {"multiple": True},
    {"arguments": "invalid json"}, {"arguments": '{"action":"execute_shell"}'},
    {"arguments": '{"action":"buy","sl_atr":-2,"tp_atr":4}'},
    {"arguments": '{"action":"sell","sl_atr":"NaN","tp_atr":4}'},
])
def test_bad_responses_hold(strategy, monkeypatch, kwargs):
    response(monkeypatch, **kwargs)
    assert strategy.generate_signal("XAUUSD", candles()).action == SignalAction.HOLD


def test_permanent_api_error_does_not_exit_worker(strategy, monkeypatch):
    import requests
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise requests.HTTPError(response=SimpleNamespace(status_code=401))

    monkeypatch.setattr("app.strategy.ai_agent.requests.post", fail)
    assert strategy.generate_signal("XAUUSD", candles()).action == SignalAction.HOLD
    assert len(calls) == 1


def test_gateway_and_cache_replay(strategy, monkeypatch):
    strategy.client.base_url = "http://localhost:20128/v1"
    calls = response(monkeypatch, "hold")
    strategy.generate_signal("XAUUSD", candles())
    strategy.generate_signal("XAUUSD", candles())
    assert len(calls) == 1
    assert calls[0]["url"] == "http://localhost:20128/v1/responses"
    assert strategy.agent.cache_hits == 1


def test_daily_context_excludes_partial_day_and_has_real_position(strategy, broker):
    frame = candles(246, tz="UTC")
    broker.execute(TradingSignal("XAUUSD", SignalAction.BUY, 1990, frame.index[200],
                                quantity=1, stop_loss=1900, take_profit=2100))
    ctx = strategy._context("XAUUSD", frame)
    assert len(ctx.d1) == 10
    assert ctx.d1.index.max() + pd.Timedelta(days=1) <= frame.index[-1] + pd.Timedelta(hours=1)
    assert ctx.broker.pos.side == "long" and ctx.broker.pos.entry_price == 1990


def test_intrahour_and_h4_data_do_not_call_agent(strategy, monkeypatch):
    calls = response(monkeypatch)
    for frequency in ("5min", "4h"):
        signal = strategy.generate_signal("XAUUSD", candles(freq=frequency))
        assert signal.action == SignalAction.HOLD and "H1" in signal.reason
    assert not calls


def test_cadence_survives_strategy_recreation(strategy, monkeypatch):
    strategy.cadence = 4
    calls = response(monkeypatch, "hold")
    for count in range(241, 249):
        strategy.generate_signal("XAUUSD", candles(count))
    assert len(calls) == 2


def test_engine_fills_next_open_and_never_exposes_execution_candle(strategy, broker):
    captured = []
    strategy.agent = SimpleNamespace(decide=lambda ctx: (captured.append(ctx) or
                                    Decision("buy", sl_atr=2, tp_atr=4, reason="test")))
    frame = candles()
    frame.iloc[-1] = [2003, 2004, 2002, 2003.5, 999]
    trading = engine(strategy, broker)
    result = trading.run_once(frame)
    position = broker.get_positions()[0]
    assert trading.timeframe == "H1"
    assert captured[0].now == frame.index[-2]
    assert captured[0].h1.Close.iloc[-1] == 2000
    assert position.entry_price == 2003 and position.stop_loss == 1999
    assert position.take_profit == 2011
    assert result.signal.time == frame.index[-1]
    assert position.quantity > 0


@pytest.mark.parametrize("action", ["close", "sell"])
def test_close_and_reverse(strategy, broker, action):
    frame = candles()
    broker.execute(TradingSignal("XAUUSD", SignalAction.BUY, 2000, frame.index[100],
                                quantity=1, stop_loss=1900, take_profit=2100))
    strategy.agent = SimpleNamespace(decide=lambda ctx: Decision(action, sl_atr=2, tp_atr=4, reason="test"))
    result = engine(strategy, broker).run_once(frame)
    assert len(result.closed_trades) == 1
    assert len(broker.get_trades()) == 1
    assert len(broker.get_positions()) == (1 if action == "sell" else 0)
    if action == "sell":
        assert broker.get_positions()[0].side == "SELL"


@pytest.mark.parametrize("action", ["buy", "sell", "close"])
def test_manual_mode_blocks_all_agent_orders(strategy, broker, action):
    frame = candles()
    broker.execute(TradingSignal("XAUUSD", SignalAction.BUY, 2000, frame.index[100],
                                quantity=1, stop_loss=1900, take_profit=2100))
    strategy.agent = SimpleNamespace(decide=lambda ctx: Decision(action, sl_atr=2, tp_atr=4, reason="test"))
    result = engine(strategy, broker, auto=False).run_once(frame)
    assert result.signal.execution_diagnostic["executed"] is False
    assert len(broker.get_positions()) == 1 and not broker.get_trades()


def test_intrabar_stops_run_on_skipped_decisions(strategy, broker):
    frame = candles(243)
    frame.iloc[-1] = [2000, 2003, 1990, 2000, 500]
    broker.execute(TradingSignal("XAUUSD", SignalAction.BUY, 2000, frame.index[100],
                                quantity=1, stop_loss=1995, take_profit=2010))
    strategy.cadence = 24
    result = engine(strategy, broker).run_once(frame)
    assert result.signal.action == SignalAction.HOLD
    assert len(result.closed_trades) == 1
    assert result.closed_trades[0].exit_price == 1995


@pytest.mark.parametrize("config", [{"warmup_days": 0}, {"decision_every_n_bars": 0},
                                    {"default_sl_atr": float("nan")}, {"h1_view_bars": 5.5}])
def test_invalid_config_rejected(config):
    with pytest.raises(ValueError):
        AIAgentStrategy(config)


def test_legacy_profile_and_strategy_menu():
    from app.factories.strategy_factory import create_strategy, get_supported_strategies
    from app.strategy.strategy_catalog import CATALOG
    strategy = create_strategy("AI_AGENT", {"min_confidence": 0.9, "stop_loss_pips": 50})
    assert strategy.cadence == 4 and strategy.cfg["DEFAULT_SL_ATR"] == 2
    label = next(s["label"] for s in get_supported_strategies() if s["value"] == "AI_AGENT")
    assert "Sol" in label and "H1" in label
    assert CATALOG["AI_AGENT"]["name"] == label


def test_worker_restart_uses_saved_position_and_decision_history(strategy, broker, monkeypatch):
    response(monkeypatch, "buy")
    engine(strategy, broker).run_once(candles(tz="UTC"))
    restarted = AIAgentStrategy({"decision_every_n_bars": 1})
    restarted.cfg["CACHE_DIR"] = strategy.cfg["CACHE_DIR"]
    calls = response(monkeypatch, "close")
    result = engine(restarted, broker).run_once(candles(242, tz="UTC"))
    assert result.signal.action == SignalAction.CLOSE
    snapshot = calls[0]["json"]["input"][0]["content"]
    assert "Open position: LONG" in snapshot
    assert "Recent decisions:" in snapshot
    assert not broker.get_positions() and len(broker.get_trades()) == 1


def test_cost_aware_agent_fill_is_not_delayed_twice(strategy):
    from app.brokers.cost_aware_backtest_broker import CostAwareBacktestBroker
    broker = CostAwareBacktestBroker()
    strategy.agent = SimpleNamespace(decide=lambda ctx: Decision("buy", sl_atr=2, tp_atr=4, reason="test"))
    trading = TradingEngine(None, strategy, broker, "XAUUSD", "H1", respect_trading_mode=False)
    frame = candles()
    frame.iloc[-1] = [2003, 2004, 2002, 2003, 500]
    trading.run_once(frame)
    assert broker.get_positions()[0].entry_price == 2003
    assert broker.get_positions()[0].opened_at == frame.index[-1]
    assert not broker.pending_signals


def test_dashboard_backtest_requires_h1(strategy):
    from app.backtest.backtest_service import BacktestService
    with pytest.raises(ValueError, match="requires H1"):
        BacktestService()._run_strategy(SimpleNamespace(timeframe="M5"), candles(), strategy, None)


def test_rejected_reversal_keeps_existing_position(strategy, broker):
    frame = candles()
    broker.execute(TradingSignal("XAUUSD", SignalAction.BUY, 2000, frame.index[100],
                                quantity=1, stop_loss=1900, take_profit=2100))
    strategy.agent = SimpleNamespace(decide=lambda ctx: Decision("sell", sl_atr=2, tp_atr=4, reason="test"))
    trading = engine(strategy, broker)
    trading.risk_manager.evaluate = lambda *args: SimpleNamespace(allowed=False, reason="Risk limit")
    result = trading.run_once(frame)
    assert not result.signal.execution_diagnostic["executed"]
    assert broker.get_positions()[0].side == "BUY"
    assert not broker.get_trades()
