from app.providers.mt5_provider import MT5Provider
from app.providers.yahoo_provider import YahooProvider
from app.providers.oanda_provider import OandaProvider
from app.providers.twelve_data_provider import TwelveDataProvider
from app.config import ProviderConfig
from app.config import OANDA_API_KEY, TWELVE_DATA_API_KEY
from app.factories.repository_factory import RepositoryFactory


SUPPORTED_PROVIDER_NAMES = {"mt5", "oanda", "yahoo", "twelve_data"}


def create_provider(name: str = None):
    name = (name or _configured_provider_name()).lower()

    if name == "mt5":
        provider = MT5Provider()

    elif name == "oanda":
        provider = OandaProvider(OANDA_API_KEY)

    elif name == "yahoo":
        provider = YahooProvider()

    elif name in {"twelve_data", "twelvedata"}:
        provider = TwelveDataProvider(TWELVE_DATA_API_KEY)

    else:
        raise ValueError(f"Unknown provider: {name}")

    provider.connect()

    return provider


def _configured_provider_name():
    """Use the persisted dashboard choice, with the environment as fallback."""
    repos = RepositoryFactory()
    try:
        return repos.settings.get_market_data_provider()
    finally:
        repos.close()
