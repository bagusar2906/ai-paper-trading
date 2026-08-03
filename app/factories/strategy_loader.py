from app.factories.repository_factory import RepositoryFactory
from app.factories.strategy_factory import create_strategy


def load_active_strategy():

    repos = RepositoryFactory()

    try:

        strategy = repos.strategies.get_active()

        if strategy is None:

            raise Exception(
                "No active strategy configured."
            )

        return create_strategy(

            strategy.strategy_type,

            strategy.config,

        )

    finally:

        # This is called on every /signal and /chart request (and from the
        # backtest factory) - without closing here, each call permanently
        # leaks one connection from the main app's pool.
        repos.close()