from app.database.models import SettingEntity
from app.config import ProviderConfig


class SettingsRepository:

    def __init__(self, session):

        self.session = session

    def get(self, key, default=None):

        entity = (
            self.session
            .query(SettingEntity)
            .filter_by(key=key)
            .first()
        )

        if entity is None:
            return default

        return entity.value

    def set(self, key, value):

        entity = (
            self.session
            .query(SettingEntity)
            .filter_by(key=key)
            .first()
        )

        if entity is None:

            entity = SettingEntity(
                key=key,
                value=str(value),
            )

            self.session.add(entity)

        else:

            entity.value = str(value)

        self.session.commit()

    def get_trading_mode(self):

        return self.get(
            "trading_mode",
            "MANUAL",
        )

    def get_market_data_provider(self):

        return self.get(
            "market_data_provider",
            ProviderConfig.DEFAULT_PROVIDER,
        )
