"""Paper strategy adapter for GPT_5.6_Sol_Trading_Agent's one-shot agent."""

import json
import logging
import math
import os
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import requests

from app.enums.signal_action import SignalAction
from app.models.signal import TradingSignal
from app.strategy.base import Strategy
from app.strategy.parameter import StrategyParameter
from app.strategy.sol_agent.agents import LLMAgent
from app.strategy.sol_agent.indicators import atr, compute_indicators
from app.strategy.sol_agent.market_view import MarketView
from app.strategy.sol_agent.tools import DecisionContext

logger = logging.getLogger(__name__)


class GatewayClient:
    """Keep the application's configured HTTP gateway and timeout support."""

    def __init__(self):
        self.responses = self
        self.api_key = (os.getenv("AI_API_KEY") or os.getenv("OMNIROUTE_API_KEY")
                        or os.getenv("OPENAI_API_KEY", ""))
        self.base_url = os.getenv("AI_API_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.timeout = float(os.getenv("OPENAI_TRADING_TIMEOUT_SECONDS", "20"))

    def create(self, **payload):
        response = requests.post(
            f"{self.base_url}/responses", json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"}, timeout=self.timeout,
        )
        response.raise_for_status()
        return json.loads(response.text, object_hook=lambda obj: SimpleNamespace(**obj))


class AIAgentStrategy(Strategy):
    required_timeframe = "H1"
    next_open_execution = True

    @classmethod
    def schema(cls):
        return [
            StrategyParameter(key="decision_every_n_bars", label="Decision interval (H1 candles)",
                              type="number", default=4, minimum=1, maximum=24, step=1,
                              description="Requires H1 history. Uses completed hourly and daily candles."),
            StrategyParameter(key="warmup_days", label="Warmup days", type="number",
                              default=10, minimum=2, maximum=60, step=1),
            StrategyParameter(key="h1_view_bars", label="Hourly candles supplied to agent", type="number",
                              default=24, minimum=5, maximum=200, step=1),
            StrategyParameter(key="d1_view_bars", label="Daily candles supplied to agent", type="number",
                              default=10, minimum=5, maximum=60, step=1),
            StrategyParameter(key="default_sl_atr", label="Default stop distance (ATR)", type="number",
                              default=2.0, minimum=0.25, maximum=20, step=0.25),
            StrategyParameter(key="default_tp_atr", label="Default target distance (ATR)", type="number",
                              default=4.0, minimum=0.25, maximum=20, step=0.25),
        ]

    def __init__(self, config):
        # Existing AI_AGENT profiles retain their ID. Obsolete confidence/pip/
        # stride settings intentionally do not alter this agent's policy.
        self.cfg = {
            "MODEL": os.getenv("OPENAI_TRADING_MODEL", "gpt-5.6-sol"),
            "MAX_TOKENS": 1000, "REASONING_EFFORT": "medium", "TEMPERATURE": 0.2,
            "ANONYMIZE": True, "ALLOW_SHORT": True, "POSITION_FRACTION": 0.95,
            "FEE_RATE": 0.0005, "SLIPPAGE_RATE": 0.0002,
            "DEFAULT_SL_ATR": float(config.get("default_sl_atr", 2)),
            "DEFAULT_TP_ATR": float(config.get("default_tp_atr", 4)),
            "H1_VIEW_BARS": int(config.get("h1_view_bars", 24)),
            "D1_VIEW_BARS": int(config.get("d1_view_bars", 10)),
            "CACHE_DIR": str(Path(__file__).resolve().parents[2] / "data" / "sol_agent_cache"),
        }
        self.cadence = int(config.get("decision_every_n_bars", 4))
        self.warmup_days = int(config.get("warmup_days", 10))
        for field in self.schema():
            number = float(config.get(field.key, field.default))
            if not math.isfinite(number) or not field.minimum <= number <= field.maximum:
                raise ValueError(f"{field.label} must be between {field.minimum} and {field.maximum}")
            if field.step == 1 and number != int(number):
                raise ValueError(f"{field.label} must be a whole number")
        self.client = GatewayClient()
        self.broker = None
        self.agent = None
        self.journal = []

    @property
    def name(self):
        return "GPT 5.6 Sol Trading Agent"

    @property
    def minimum_bars(self):
        return self.warmup_days * 24

    def prepare(self, df):
        return df.copy()

    def bind_broker(self, broker):
        self.broker = broker

    def generate_signal(self, symbol, df):
        price, stamp = float(df.iloc[-1]["Close"]), df.index[-1]
        hold = lambda reason: TradingSignal(symbol, SignalAction.HOLD, price, stamp, reason=reason)
        if not self.can_run(df):
            return hold("Not enough hourly history for agent warmup")
        if not isinstance(df.index, pd.DatetimeIndex) or not df.index.is_monotonic_increasing or df.index.has_duplicates:
            return hold("Agent requires sorted, unique H1 candles")
        differences = df.index.to_series().diff().dropna()
        if (differences < pd.Timedelta(hours=1)).any() or not (differences == pd.Timedelta(hours=1)).any():
            return hold("GPT Sol agent requires H1 candles")
        # Timestamp cadence remains stable when workers restart or roll history.
        if int(pd.Timestamp(stamp).timestamp() // 3600) % self.cadence:
            return hold(f"Agent evaluates every {self.cadence} H1 candles")
        if not self.client.api_key:
            return hold("No AI gateway API key is configured")
        if self.broker is None:
            return hold("Agent requires paper-account context from the trading engine")
        try:
            ctx = self._context(symbol, df)
            if self.agent is None:
                self.agent = LLMAgent(self.cfg, client=self.client)
            decision = self.agent.decide(ctx)
            action = SignalAction(decision.action.upper())
            sl, tp = None, None
            if action in (SignalAction.BUY, SignalAction.SELL):
                volatility = float(atr(df, 14).iloc[-1])
                stop = float(decision.sl_atr if decision.sl_atr is not None else self.cfg["DEFAULT_SL_ATR"])
                target = float(decision.tp_atr if decision.tp_atr is not None else self.cfg["DEFAULT_TP_ATR"])
                if not all(math.isfinite(x) for x in (volatility, stop, target)) or volatility <= 0:
                    raise ValueError("Invalid ATR risk levels")
                if not (0.25 <= stop <= 20 and 0.25 <= target <= 20):
                    raise ValueError("ATR multipliers out of range")
                direction = 1 if action == SignalAction.BUY else -1
                sl, tp = price - direction * volatility * stop, price + direction * volatility * target
            self.journal.append({"label": ctx.view.tlabel(stamp), "action": decision.action,
                                 "reason": decision.reason[:140]})
            self.journal = self.journal[-5:]
            return TradingSignal(symbol, action, price, stamp, reason=decision.reason[:255],
                                 stop_loss=sl, take_profit=tp)
        except (Exception, SystemExit) as exc:
            logger.warning("GPT Sol decision unavailable: %s", exc)
            return hold("Agent decision unavailable; holding")

    def _context(self, symbol, h1):
        # Candle timestamps are opens. Only days ending before the visible
        # hourly candle's end are complete. Drop a truncated first day too.
        daily = h1.resample("1D", label="left", closed="left").agg({
            "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
        }).dropna(subset=["Open", "Close"])
        daily = daily[daily.index + pd.Timedelta(days=1) <= h1.index[-1] + pd.Timedelta(hours=1)]
        first_day = h1.index[0].normalize()
        if h1.index[0] != first_day:
            first_day += pd.Timedelta(days=1)
        daily = daily[daily.index >= first_day]
        account = self.broker.get_account()
        self.cfg.update(ASSET_NAME=symbol, START_EQUITY=getattr(self.broker, "initial_balance", account.balance))
        view = MarketView(self.cfg, float(h1.Close.iloc[0]), h1.index[0])
        positions = [p for p in self.broker.get_positions() if p.symbol == symbol]
        pos = None
        if positions:
            p = positions[0]
            notional = abs(p.quantity * p.entry_price)
            opened = pd.Timestamp(p.opened_at)
            if h1.index.tz is not None and opened.tzinfo is None:
                opened = opened.tz_localize(h1.index.tz)
            pos = SimpleNamespace(
                side="long" if p.side == SignalAction.BUY else "short", entry_price=p.entry_price,
                units=p.quantity, notional=notional, size_fraction=notional / max(account.equity, 1),
                sl=p.stop_loss, tp=p.take_profit, entry_time=opened,
                entry_bar=int(h1.index.searchsorted(opened)),
            )
        trades = [t for t in self.broker.get_trades() if t.symbol == symbol]
        closed = [{"side": "long" if t.side == SignalAction.BUY else "short",
                   "pnl_pct": 100 * t.pnl / max(abs(t.entry_price * t.quantity), 1),
                   "exit_reason": "paper account close"} for t in trades[-5:]]
        snapshot = SimpleNamespace(pos=pos, trades=closed, fees_paid=0.0,
                                   realized=account.balance - self.cfg["START_EQUITY"],
                                   equity=lambda price: account.equity)
        journal = self.journal
        repos = getattr(self.broker, "repos", None)
        if repos is not None:
            recent = [s for s in repos.signals.get_recent(100) if s.symbol == symbol and
                      pd.Timestamp(s.time).replace(tzinfo=None) <= pd.Timestamp(h1.index[-1]).replace(tzinfo=None)]
            journal = [{"label": view.tlabel(pd.Timestamp(s.time).tz_localize(h1.index.tz)
                         if h1.index.tz is not None and pd.Timestamp(s.time).tzinfo is None else s.time),
                        "action": getattr(s.action, "value", s.action), "reason": s.reason} for s in recent[-5:]]
        return DecisionContext(h1.index[-1], len(h1) - 1, h1, daily,
                               compute_indicators(h1, daily), view, snapshot, journal, self.cfg)
