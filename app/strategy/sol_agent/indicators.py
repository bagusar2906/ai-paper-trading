"""Indicators - always computed on the visible slice only [GUARD 4]."""

from __future__ import annotations

import math
from typing import Any, Dict

import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _num(x, nd: int = 2):
    try:
        x = float(x)
        if math.isnan(x) or math.isinf(x):
            return None
        return round(x, nd)
    except (TypeError, ValueError):
        return None


def compute_indicators(h1: pd.DataFrame, d1: pd.DataFrame) -> Dict[str, Any]:
    """Scale-free snapshot (percent / ratio values only, so anonymization holds
    even inside get_indicators)."""
    out: Dict[str, Any] = {}
    c = h1["Close"]
    out["h1_ret_1h_pct"] = _num((c.iloc[-1] / c.iloc[-2] - 1) * 100) if len(c) > 1 else None
    out["h1_ret_24h_pct"] = _num((c.iloc[-1] / c.iloc[-25] - 1) * 100) if len(c) > 25 else None
    out["h1_rsi14"] = _num(rsi(c, 14).iloc[-1], 1)
    for n in (20, 50, 200):
        out[f"h1_dist_ema{n}_pct"] = _num((c.iloc[-1] / ema(c, n).iloc[-1] - 1) * 100) if len(c) >= n else None
    out["h1_atr14_pct"] = _num(atr(h1, 14).iloc[-1] / c.iloc[-1] * 100)
    if len(d1) >= 2:
        dc = d1["Close"]
        out["d1_ret_1d_pct"] = _num((dc.iloc[-1] / dc.iloc[-2] - 1) * 100)
        out["d1_ret_7d_pct"] = _num((dc.iloc[-1] / dc.iloc[-8] - 1) * 100) if len(dc) > 8 else None
        out["d1_rsi14"] = _num(rsi(dc, 14).iloc[-1], 1) if len(dc) >= 15 else None
        out["d1_dist_ema20_pct"] = _num((dc.iloc[-1] / ema(dc, 20).iloc[-1] - 1) * 100) if len(dc) >= 20 else None
        out["d1_atr14_pct"] = _num(atr(d1, 14).iloc[-1] / dc.iloc[-1] * 100) if len(d1) >= 15 else None
        if len(d1) >= 20:
            hh = float(d1["High"].rolling(20).max().iloc[-1])
            ll = float(d1["Low"].rolling(20).min().iloc[-1])
            rng = hh - ll
            out["d1_donchian20_pos_pct"] = _num(100 * (float(c.iloc[-1]) - ll) / rng) if rng > 0 else None
    return out
