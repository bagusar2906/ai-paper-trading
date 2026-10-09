"""Market view - anonymization lives here [GUARD 5]."""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

import pandas as pd


class MarketView:
    """Formats candles/prices/times for the agent. In anonymized mode the model
    sees 'Asset X', an index rebased so the first candle of the dataset ~= 100,
    and relative time labels (T+3d07h) instead of calendar dates."""

    def __init__(self, cfg: Dict[str, Any], base_price: float, trade_start: pd.Timestamp):
        self.anon = bool(cfg["ANONYMIZE"])
        self.name = str(cfg.get("ASSET_NAME", "BTC/USD"))
        self.scale = 100.0 / base_price if base_price else 1.0
        self.trade_start = pd.Timestamp(trade_start)

    @property
    def asset(self) -> str:
        return "Asset X" if self.anon else self.name

    def px(self, p) -> Optional[float]:
        if p is None:
            return None
        p = float(p)
        if math.isnan(p):
            return None
        return round(p * self.scale, 2) if self.anon else round(p, 2)

    def tlabel(self, ts) -> str:
        ts = pd.Timestamp(ts)
        if not self.anon:
            return ts.strftime("%Y-%m-%d %H:%M")
        total_h = int((ts - self.trade_start).total_seconds() // 3600)
        sign = "+" if total_h >= 0 else "-"
        total_h = abs(total_h)
        return f"T{sign}{total_h // 24}d{total_h % 24:02d}h"

    def candle_lines(self, dfv: pd.DataFrame, n: int, tf: str, vol_ref: float) -> str:
        tail = dfv.tail(n)
        m = len(tail)
        lines = []
        for k, (ts, row) in enumerate(tail.iterrows()):
            off = m - 1 - k
            if self.anon:
                tag = f"{'h' if tf == '1h' else 'd'}-{off:02d}"
            else:
                tag = pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M" if tf == "1h" else "%Y-%m-%d")
            v = ""
            if vol_ref and vol_ref > 0 and "Volume" in row.index:
                v = f" | V {float(row['Volume']) / vol_ref:.1f}x"
            lines.append(
                f"{tag} | O {self.px(row['Open'])} H {self.px(row['High'])}"
                f" L {self.px(row['Low'])} C {self.px(row['Close'])}{v}"
            )
        return "\n".join(lines)
