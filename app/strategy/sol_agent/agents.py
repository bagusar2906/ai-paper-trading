"""Agents: LLMAgent (GPT via the OpenAI API), MockAgent, RandomAgent."""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .indicators import ema
from .tools import ORDER_TOOLS, DecisionContext, build_market_snapshot, exec_tool


@dataclass
class Decision:
    action: str = "hold"
    size_fraction: float = 0.0
    sl_atr: Optional[float] = None
    tp_atr: Optional[float] = None
    reason: str = ""
    reasoning_text: str = ""
    transcript: list = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False


def build_system_prompt(cfg: Dict[str, Any]) -> str:
    fee_bps = cfg["FEE_RATE"] * 1e4
    slip_bps = cfg["SLIPPAGE_RATE"] * 1e4
    if cfg["ANONYMIZE"]:
        asset = ("You are trading 'Asset X', a liquid market. Its identity, calendar dates "
                 "and price scale are deliberately hidden: prices are an index (history starts near 100) and "
                 "times are offsets from the start of live trading (T+0d00h). Do NOT try to guess which asset "
                 "or which time period this is - reason only from the provided market snapshot.")
    else:
        asset = f"You are trading {cfg.get('ASSET_NAME', 'BTC/USD')}. Timestamps are exchange time."
    short_rule = "You may go long or short." if cfg["ALLOW_SHORT"] else \
        "Long-only account: 'sell' simply closes an open long."
    return f"""You are an autonomous trading agent. {asset}

You make decisions on 1-hour candles and also receive daily candles for higher-timeframe context. Only COMPLETED candles are ever shown to you - you never see the future.

Account rules:
- One position at a time. {short_rule}
- Costs: {fee_bps:.1f} bps fee per side plus ~{slip_bps:.1f} bps slippage. Overtrading is expensive.
- Orders execute at the NEXT 1-hour open, never at the close you just observed.

Each decision cycle:
1. Review the complete market snapshot in the user message.
2. Reason briefly (under ~120 words).
3. Call place_order EXACTLY ONCE: buy | sell | close | hold.

Risk management: when opening, set sl_atr and tp_atr (stop/target distances in ATR(14, 1h) multiples; typical sl 1.5-3, tp 2-6). Between your decision cycles the stop and target are monitored on every 1-hour bar.

Be selective. Holding is often the right call but we still need to enter the market in the direction of the momentum at the right entry moment like with a slight retracement for example. Your performance is benchmarked against buy-and-hold and against random agents and you need to beat this."""


def _responses_tool(tool: dict) -> dict:
    """Convert a Chat-style function schema to the flat Responses API shape."""
    fn = tool["function"]
    return {
        "type": "function",
        "name": fn["name"],
        "description": fn.get("description", ""),
        "parameters": fn.get("parameters", {}),
        # Chat Completions treated this schema as non-strict. Keep the same
        # optional/default behavior when moving it to Responses.
        "strict": False,
    }


RESPONSE_ORDER_TOOLS = [_responses_tool(tool) for tool in ORDER_TOOLS]


def _ser_tool_call(tc) -> dict:
    """Serialize a Responses API function call for the transcript log."""
    return {
        "id": getattr(tc, "call_id", None) or getattr(tc, "id", None),
        "name": getattr(tc, "name", None),
        "arguments": getattr(tc, "arguments", None),
    }


def _supports_reasoning(model: str) -> bool:
    m = str(model).lower()
    return m.startswith(("gpt-5", "o1", "o3", "o4"))


def _http_status(exc: Exception) -> Optional[int]:
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


class LLMAgent:
    """GPT in a one-shot decision call, with a disk cache so reruns cost $0."""
    name = "llm"

    def __init__(self, cfg: Dict[str, Any], client=None):
        if client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise SystemExit("Real mode needs the SDK:  pip install openai   (or run with --mock)")
            if not os.environ.get("OPENAI_API_KEY"):
                raise SystemExit("Set OPENAI_API_KEY (or run with --mock).")
            # This class owns its retry/backoff policy below. Disabling SDK
            # retries prevents one logical attempt from multiplying into three.
            client = OpenAI(max_retries=0)
        self.client = client
        self.cfg = cfg
        self.system = build_system_prompt(cfg) + (
            "\nApplication risk controls determine the final position size. "
            "size_fraction is advisory only. Stops and targets are ATR multiples."
        )
        self.cache_dir = Path(cfg["CACHE_DIR"])
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.total_in = 0
        self.total_out = 0
        self.api_calls = 0
        self.cache_hits = 0

    def _cache_key(self, ctx: DecisionContext, snapshot: str) -> str:
        fp = ",".join(f"{x:.2f}" for x in ctx.h1["Close"].tail(8))
        pos = ctx.broker.pos
        ps = f"{pos.side}:{pos.entry_price:.2f}" if pos else "flat"
        raw = "|".join([
            "oneshot-responses-v1",
            self.cfg["MODEL"], str(self.cfg["ANONYMIZE"]), str(self.cfg.get("ASSET_NAME", "")),
            str(self.cfg["MAX_TOKENS"]), str(self.cfg.get("REASONING_EFFORT")),
            hashlib.sha256(self.system.encode()).hexdigest()[:12],
            hashlib.sha256(json.dumps(RESPONSE_ORDER_TOOLS, sort_keys=True).encode()).hexdigest()[:12],
            hashlib.sha256(snapshot.encode()).hexdigest()[:16],
            str(ctx.now), fp, ps, str(len(ctx.journal)), f"{ctx.broker.realized:.2f}",
        ])
        return hashlib.sha256(raw.encode()).hexdigest()

    def _call(self, messages):
        last = None
        for attempt in range(3):
            try:
                self.api_calls += 1
                params = {
                    "model": self.cfg["MODEL"],
                    "instructions": self.system,
                    "input": messages,
                    "max_output_tokens": self.cfg["MAX_TOKENS"],
                    "tools": RESPONSE_ORDER_TOOLS,
                    "tool_choice": {"type": "function", "name": "place_order"},
                    "parallel_tool_calls": False,
                    "store": False,
                }
                effort = self.cfg.get("REASONING_EFFORT")
                if effort is not None and _supports_reasoning(self.cfg["MODEL"]):
                    params["reasoning"] = {"effort": effort}
                if self.cfg.get("TEMPERATURE") is not None and not _supports_reasoning(self.cfg["MODEL"]):
                    params["temperature"] = self.cfg["TEMPERATURE"]
                return self.client.responses.create(**params)
            except Exception as e:  # noqa: BLE001 - network layer, retry then degrade to hold
                last = e
                status = _http_status(e)
                if status is not None and 400 <= status < 500 and status not in (408, 409, 429):
                    raise SystemExit(f"OpenAI API rejected the request (HTTP {status}): {e}") from e
                if attempt < 2:
                    time.sleep(2 ** attempt)
        print(f"  [warn] API failed after retries: {last}")
        return None

    def decide(self, ctx: DecisionContext) -> Decision:
        snapshot = build_market_snapshot(ctx)
        key = self._cache_key(ctx, snapshot)
        cf = self.cache_dir / f"{key}.json"
        if cf.exists():                                   # replay -> free rerun
            try:
                d = json.loads(cf.read_text())
                d["cached"] = True
                self.cache_hits += 1
                return Decision(**d)
            except Exception:
                pass
        user = snapshot
        messages: list = [{"role": "user", "content": user}]
        transcript: list = [{"role": "user", "content": user}]
        reasoning: List[str] = []
        t_in = t_out = 0
        cacheable = False
        fallback_reason: Optional[str] = None
        resp = self._call(messages)
        if resp is None:
            fallback_reason = "api_error -> hold"
        else:
            usage = getattr(resp, "usage", None)
            t_in += int(getattr(usage, "input_tokens", 0) or 0)
            t_out += int(getattr(usage, "output_tokens", 0) or 0)
            status = getattr(resp, "status", None)
            visible = (getattr(resp, "output_text", "") or "").strip()
            output = list(getattr(resp, "output", None) or [])
            tool_calls = [item for item in output if getattr(item, "type", None) == "function_call"]
            assistant_log = {"role": "assistant", "content": visible or None,
                             "tool_calls": [_ser_tool_call(tc) for tc in tool_calls]}
            if status is not None:
                assistant_log["status"] = status
            transcript.append(assistant_log)
            if visible:
                reasoning.append(visible)
            response_complete = status == "completed"
            if not response_complete:
                details = getattr(resp, "incomplete_details", None)
                why = getattr(details, "reason", None) or "unknown"
                fallback_reason = f"incomplete response ({why}) -> hold"
                print(f"  [warn] API response incomplete: {why}")
            for tc in tool_calls:
                if not response_complete or len(tool_calls) != 1:
                    fallback_reason = "incomplete or multiple orders -> hold"
                    break
                if getattr(tc, "name", None) != "place_order":
                    continue
                try:
                    args = json.loads(getattr(tc, "arguments", None) or "{}")
                    if not isinstance(args, dict) or str(args.get("action", "")).lower() not in (
                            "buy", "sell", "close", "hold"):
                        raise ValueError("place_order arguments did not contain a valid action")
                except (json.JSONDecodeError, TypeError, ValueError):
                    fallback_reason = "invalid place_order arguments -> hold"
                    continue
                out = exec_tool("place_order", args, ctx)
                transcript.append({"role": "tool_result", "name": tc.name, "content": out})
                cacheable = response_complete and ctx.pending is not None
                break
        if ctx.pending is None:
            ctx.pending = {"action": "hold", "size_fraction": 0.0,
                           "sl_atr": None, "tp_atr": None,
                           "reason": fallback_reason or "no order placed -> hold"}
        self.total_in += t_in
        self.total_out += t_out
        p = ctx.pending
        dec = Decision(action=p["action"], size_fraction=p["size_fraction"], sl_atr=p["sl_atr"],
                       tp_atr=p["tp_atr"], reason=p["reason"], reasoning_text="\n\n".join(reasoning),
                       transcript=transcript, input_tokens=t_in, output_tokens=t_out, cached=False)
        if cacheable:
            try:
                cf.write_text(json.dumps(asdict(dec), default=str))
            except Exception:
                pass
        return dec


class MockAgent:
    """Deterministic EMA20/EMA50 policy with fake 'reasoning'. Zero API cost -
    use it to test the whole pipeline and to demo the video without a key."""
    name = "mock"

    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg

    def decide(self, ctx: DecisionContext) -> Decision:
        c = ctx.h1["Close"]
        f = float(ema(c, 20).iloc[-1])
        s = float(ema(c, 50).iloc[-1])
        r = ctx.ind.get("h1_rsi14")
        pos = ctx.broker.pos
        bull = f > s
        action, reason = "hold", f"Mock policy: no regime change (EMA20 {'>' if bull else '<'} EMA50, RSI {r})."
        if bull and (pos is None or pos.side == "short"):
            action = "buy"
            reason = f"Mock policy: EMA20 above EMA50 ({f:.2f} > {s:.2f}), RSI {r}. Going long."
        elif not bull:
            if self.cfg["ALLOW_SHORT"] and (pos is None or pos.side == "long"):
                action = "sell"
                reason = f"Mock policy: EMA20 below EMA50 ({f:.2f} < {s:.2f}), RSI {r}. Going short."
            elif pos is not None and pos.side == "long":
                action = "close"
                reason = "Mock policy: EMA20 dropped below EMA50 - closing long."
        return Decision(action=action, size_fraction=self.cfg["POSITION_FRACTION"],
                        sl_atr=2.0, tp_atr=4.0, reason=reason, reasoning_text=reason)


class RandomAgent:
    """Baseline control: same cadence, same broker mechanics, coin-flip decisions."""
    name = "random"

    def __init__(self, seed: int, cfg: Dict[str, Any]):
        self.rng = random.Random(seed)
        self.cfg = cfg

    def decide(self, ctx: DecisionContext) -> Decision:
        pos = ctx.broker.pos
        r = self.rng.random()
        if pos is None:
            if r < 0.30:
                side = "buy"
                if self.cfg["ALLOW_SHORT"] and self.rng.random() < 0.5:
                    side = "sell"
                return Decision(action=side, size_fraction=self.cfg["POSITION_FRACTION"],
                                sl_atr=2.0, tp_atr=4.0, reason="random open")
            return Decision(action="hold", reason="random hold")
        if r < 0.20:
            return Decision(action="close", reason="random close")
        return Decision(action="hold", reason="random hold")
