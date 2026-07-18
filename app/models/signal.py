
from dataclasses import dataclass
from typing import Optional

@dataclass
class TradingSignal:
    symbol: str
    action: str          # BUY, SELL, HOLD
    price: float
    time: str
    
    ema: float
    rsi: float
    adx: float
    plus_di: float
    minus_di: float

    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    reason: str = ""
