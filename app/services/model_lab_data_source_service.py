"""A saved Model Lab preference, separate from the trading data source."""
from app.factories.provider_factory import SUPPORTED_PROVIDER_NAMES
from app.factories.repository_factory import RepositoryFactory


class ModelLabDataSourceService:
    KEY = "model_lab_data_source"

    @staticmethod
    def validate(value):
        if not isinstance(value, str) or value not in SUPPORTED_PROVIDER_NAMES | {"trading"}:
            raise ValueError("data_source must be trading, mt5, oanda, yahoo, or twelve_data")
        return value

    def __init__(self, repository_factory=RepositoryFactory):
        self.repository_factory = repository_factory

    def get(self):
        repos = self.repository_factory()
        try:
            source = repos.settings.get(self.KEY, "trading")
            try:
                self.validate(source)
            except ValueError:
                source = "trading"
            return {"data_source": source}
        finally:
            repos.close()

    def set(self, value):
        source = self.validate(value)
        repos = self.repository_factory()
        try:
            repos.settings.set(self.KEY, source)
            return {"data_source": source}
        finally:
            repos.close()
