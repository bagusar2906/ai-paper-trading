from dataclasses import dataclass, field

from app.models.account import Account
from app.models.position import Position
from app.models.signal import TradingSignal
from app.models.trade import Trade


@dataclass
class EngineResult:

    signal: TradingSignal | None = None

    position: Position | None = None

    closed_trades: list[Trade] = field(default_factory=list)

    account: Account | None = None

    message: str = ""