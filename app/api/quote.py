from dataclasses import asdict, dataclass

from fastapi import APIRouter

from app.config import TradingConfig
from app.factories.provider_factory import create_provider

router = APIRouter()

# Simple synthetic spread since providers only expose a single last price,
# not real bid/ask. XAUUSD: 1 pip = 0.1 price units (see config.py).
QUOTE_SPREAD_PIPS = 3


@dataclass
class Quote:
    symbol: str
    bid: float
    ask: float


@router.get("/quote")
def get_quote(symbol: str = TradingConfig.SYMBOL):

    provider = create_provider()

    try:
        price = provider.get_current_price(symbol)
    finally:
        provider.disconnect()

    half_spread = (QUOTE_SPREAD_PIPS * TradingConfig.PIP_SIZE) / 2

    return asdict(Quote(
        symbol=symbol,
        bid=price - half_spread,
        ask=price + half_spread,
    ))
