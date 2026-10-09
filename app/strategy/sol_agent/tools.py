"""Decision context + the agent's tools (schemas in OpenAI function-calling format)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

from .market_view import MarketView


@dataclass
class DecisionContext:
    now: pd.Timestamp
    bar_index: int
    h1: pd.DataFrame          # [GUARD 1] visible slice only: df.iloc[:i+1]
    d1: pd.DataFrame          # [GUARD 2] completed daily bars from that slice
    ind: Dict[str, Any]
    view: MarketView
    broker: Any
    journal: List[dict]
    cfg: Dict[str, Any]
    pending: Optional[dict] = None   # set by the place_order tool


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_price",
            "description": ("Return recent OHLC candles (completed candles only, most recent last). "
                            "Use timeframe '1h' for the trading timeframe and '1d' for higher-timeframe context."),
            "parameters": {
                "type": "object",
                "properties": {
                    "timeframe": {"type": "string", "enum": ["1h", "1d"]},
                    "bars": {"type": "integer", "minimum": 5, "maximum": 200,
                             "description": "How many candles (default 24 for 1h; default/max 10 for 1d)"},
                },
                "required": ["timeframe"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_indicators",
            "description": ("Technical snapshot on both timeframes (RSI, EMA distances, ATR%, returns, "
                            "Donchian position). All values are scale-free and computed only on data available now."),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_position",
            "description": "Current position, equity, fees, recent closed trades and your recent decisions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": ("Submit your single decision for this cycle. buy = open/keep long, sell = open/keep short, "
                            "close = flatten, hold = do nothing. Executes at the NEXT 1h open. Call exactly once per cycle."),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["buy", "sell", "close", "hold"]},
                    "size_fraction": {"type": "number", "minimum": 0.05, "maximum": 1.0,
                                      "description": "Fraction of equity (default 0.95)"},
                    "sl_atr": {"type": "number", "minimum": 0.25, "maximum": 20,
                               "description": "Stop distance in ATR(14, 1h) multiples"},
                    "tp_atr": {"type": "number", "minimum": 0.25, "maximum": 20,
                               "description": "Target distance in ATR(14, 1h) multiples"},
                    "reason": {"type": "string", "description": "One-line rationale (goes in the trade log)"},
                },
                "required": ["action", "reason"],
            },
        },
    },
]

ORDER_TOOLS = [TOOLS[-1]]


def exec_tool(name: str, args: Dict[str, Any], ctx: DecisionContext) -> str:
    cfg = ctx.cfg
    if name == "get_price":
        tf = str(args.get("timeframe", "1h"))
        dfv = ctx.d1 if tf == "1d" else ctx.h1
        if dfv.empty:
            return f"No completed {tf} candles available."
        default_n = cfg["D1_VIEW_BARS"] if tf == "1d" else cfg["H1_VIEW_BARS"]
        max_n = cfg["D1_VIEW_BARS"] if tf == "1d" else 200
        n = max(5, min(int(args.get("bars") or default_n), max_n, len(dfv)))
        assert dfv.index[-1] <= ctx.now, "lookahead breach"   # belt & braces
        # volume shown as a multiple of the SAME timeframe's recent average
        vol_ref = float(dfv["Volume"].tail(24 * 30 if tf == "1h" else 30).mean() or 0.0)
        head = f"{ctx.view.asset} {tf} candles (last {n}, completed only, most recent last):"
        return head + "\n" + ctx.view.candle_lines(dfv, n, tf, vol_ref)

    if name == "get_indicators":
        lines = [f"{k} = {v if v is not None else 'n/a'}" for k, v in ctx.ind.items()]
        return "Indicator snapshot (data up to now only):\n" + "\n".join(lines)

    if name == "check_position":
        b = ctx.broker
        c = float(ctx.h1["Close"].iloc[-1])
        eq = b.equity(c)
        out = [
            f"Equity: ${eq:,.2f} (start ${cfg['START_EQUITY']:,.2f}, {100 * (eq / cfg['START_EQUITY'] - 1):+.2f}%)",
            f"Fees paid so far: ${b.fees_paid:,.2f}",
        ]
        if b.pos:
            p = b.pos
            d = 1.0 if p.side == "long" else -1.0
            upnl = d * p.units * (c - p.entry_price)
            out.append(
                f"Open position: {p.side.upper()} {p.size_fraction:.0%} of equity"
                f" | entry {ctx.view.px(p.entry_price)} | now {ctx.view.px(c)}"
                f" | unrealized {100 * upnl / p.notional:+.2f}%"
                f" | SL {ctx.view.px(p.sl)} TP {ctx.view.px(p.tp)}"
                f" | opened {ctx.view.tlabel(p.entry_time)} ({ctx.bar_index - p.entry_bar} bars ago)"
            )
        else:
            out.append("Open position: none (flat)")
        if b.trades:
            out.append("Last closed trades: " + " | ".join(
                f"{tr['side'].upper()} {tr['pnl_pct']:+.2f}% ({tr['exit_reason']})" for tr in b.trades[-5:]))
        if ctx.journal:
            out.append("Recent decisions:")
            for j in ctx.journal[-5:]:
                out.append(f"  {j['label']}: {j['action'].upper()} - {j['reason']}")
        return "\n".join(out)

    if name == "place_order":
        action = str(args.get("action", "hold")).lower()
        if action not in ("buy", "sell", "close", "hold"):
            action = "hold"
        if ctx.pending is not None:
            return "An order was already submitted this cycle; ignoring this one."
        ctx.pending = {
            "action": action,
            "size_fraction": float(args.get("size_fraction") or cfg["POSITION_FRACTION"]),
            "sl_atr": float(args["sl_atr"]) if args.get("sl_atr") is not None else cfg["DEFAULT_SL_ATR"],
            "tp_atr": float(args["tp_atr"]) if args.get("tp_atr") is not None else cfg["DEFAULT_TP_ATR"],
            "reason": str(args.get("reason") or "")[:300],
        }
        return f"Order received: {action.upper()}. It will execute at the next 1h open. Decision cycle complete."

    return f"Unknown tool: {name}"


def build_market_snapshot(ctx: DecisionContext) -> str:
    """Build the complete one-shot prompt payload from data already visible now."""
    latest = ctx.view.px(float(ctx.h1["Close"].iloc[-1]))
    return "\n\n".join([
        (f"Decision cycle at {ctx.view.tlabel(ctx.now)}. The latest 1-hour candle "
         f"has just closed at {latest}."),
        "The backtester prepared this snapshot from completed candles only. "
        "Use it directly; do not request market data.",
        "1H price context:\n" + exec_tool("get_price", {"timeframe": "1h"}, ctx),
        "1D price context:\n" + exec_tool("get_price", {"timeframe": "1d"}, ctx),
        exec_tool("get_indicators", {}, ctx),
        exec_tool("check_position", {}, ctx),
        "Return exactly one place_order tool call for this decision cycle.",
    ])
