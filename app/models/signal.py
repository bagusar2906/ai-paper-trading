from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TradingSignal:
    symbol: str
    action: str          # BUY / SELL / HOLD
    price: float
    time: datetime

    reason: str = ""

    # Indicator snapshot at signal time — used for logging/DB storage and
    # by any strategy that wants to expose what drove the decision.
    ema: Optional[float] = None
    rsi: Optional[float] = None
    adx: Optional[float] = None
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None

    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    confidence: float = 1.0