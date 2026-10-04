from dataclasses import dataclass


@dataclass
class SettingsRequest:

    trading_mode: str | None = None
    market_data_provider: str | None = None
