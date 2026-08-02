from app.factories.repository_factory import RepositoryFactory
from app.factories.strategy_factory import create_strategy


def load_active_strategy():

    repos = RepositoryFactory()

    strategy = repos.strategies.get_active()

    if strategy is None:

        raise Exception(
            "No active strategy configured."
        )

    return create_strategy(

        strategy.strategy_type,

        strategy.config,

    )