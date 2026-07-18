from app.providers.mt5_provider import MT5Provider
from app.providers.yahoo_provider import YahooProvider
from app.providers.oanda_provider import OandaProvider
from app.config import ProviderConfig
from app.config import OANDA_API_KEY


def create_provider(name: str = None):
    name = (name or ProviderConfig.DEFAULT_PROVIDER).lower()

    if name == "mt5":
        provider = MT5Provider()

    elif name == "oanda":
        provider = OandaProvider(OANDA_API_KEY)

    elif name == "yahoo":
        provider = YahooProvider()

    else:
        raise ValueError(f"Unknown provider: {name}")

    provider.connect()

    return provider