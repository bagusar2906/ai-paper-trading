import json

from app.factories.repository_factory import RepositoryFactory
from app.factories.strategy_factory import create_strategy


def load_active_strategy():

    repos = RepositoryFactory()

    entity = repos.strategies.get_active()

    if entity is None:

        raise Exception(
            "No active strategy configured."
        )

    return create_strategy(

        entity.strategy_type,

        json.loads(
            entity.config_json
        ),

    )