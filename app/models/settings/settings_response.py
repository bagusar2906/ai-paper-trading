from dataclasses import dataclass


@dataclass
class SettingsResponse:

    trading_mode: str
    market_data_provider: str
