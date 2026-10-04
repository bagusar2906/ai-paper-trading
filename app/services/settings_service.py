import logging

from app.enums.trading_mode import TradingMode
from app.models.settings.settings_request import SettingsRequest
from app.models.settings.settings_response import SettingsResponse
from app.factories.repository_factory import RepositoryFactory

VALID_TRADING_MODES = {mode.value for mode in TradingMode}
VALID_MARKET_DATA_PROVIDERS = {"twelve_data", "yahoo", "mt5", "oanda"}
logger = logging.getLogger(__name__)


class SettingsService:

    def get_settings(self) -> SettingsResponse:

        repos = RepositoryFactory()

        try:
            return SettingsResponse(
                trading_mode=repos.settings.get_trading_mode(),
                market_data_provider=repos.settings.get_market_data_provider(),
            )
        finally:
            repos.close()

    def update_settings(self, request: SettingsRequest) -> SettingsResponse:

        if request.trading_mode is None and request.market_data_provider is None:
            raise ValueError("At least one setting must be provided.")

        if (
            request.trading_mode is not None
            and request.trading_mode not in VALID_TRADING_MODES
        ):
            raise ValueError(
                f"Invalid trading_mode: {request.trading_mode!r}. "
                f"Must be one of {sorted(VALID_TRADING_MODES)}."
            )

        provider = None
        if request.market_data_provider is not None:
            provider = request.market_data_provider.lower()
            if provider not in VALID_MARKET_DATA_PROVIDERS:
                raise ValueError(
                    f"Invalid market_data_provider: {request.market_data_provider!r}. "
                    f"Must be one of {sorted(VALID_MARKET_DATA_PROVIDERS)}."
                )

        repos = RepositoryFactory()

        try:
            if request.trading_mode is not None:
                repos.settings.set("trading_mode", request.trading_mode)

            if provider is not None:
                repos.settings.set("market_data_provider", provider)
                logger.info("Market data provider updated provider=%s", provider)

            return SettingsResponse(
                trading_mode=repos.settings.get_trading_mode(),
                market_data_provider=repos.settings.get_market_data_provider(),
            )
        finally:
            repos.close()
