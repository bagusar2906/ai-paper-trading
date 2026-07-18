from dataclasses import dataclass
from typing import Optional

from app.models.signal import TradingSignal
from app.models.trade import Trade
from app.models.position import Position
from app.models.account import Account


@dataclass
class EngineResult:

    signal: Optional[TradingSignal] = None

    position: Optional[Position] = None

    trade: Optional[Trade] = None

    account: Optional[Account] = None

    message: str = ""