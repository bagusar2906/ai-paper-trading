from app.enums.trading_mode import TradingMode
from app.models.settings.settings_request import SettingsRequest
from app.models.settings.settings_response import SettingsResponse
from app.repositories.factory import RepositoryFactory

VALID_TRADING_MODES = {mode.value for mode in TradingMode}


class SettingsService:

    def get_settings(self) -> SettingsResponse:

        repos = RepositoryFactory()

        try:
            return SettingsResponse(
                trading_mode=repos.settings.get_trading_mode(),
            )
        finally:
            repos.close()

    def update_settings(self, request: SettingsRequest) -> SettingsResponse:

        if request.trading_mode not in VALID_TRADING_MODES:
            raise ValueError(
                f"Invalid trading_mode: {request.trading_mode!r}. "
                f"Must be one of {sorted(VALID_TRADING_MODES)}."
            )

        repos = RepositoryFactory()

        try:
            repos.settings.set("trading_mode", request.trading_mode)

            return SettingsResponse(
                trading_mode=repos.settings.get_trading_mode(),
            )
        finally:
            repos.close()
