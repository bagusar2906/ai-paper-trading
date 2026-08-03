import json

from app.factories.repository_factory import RepositoryFactory
from app.database.models import StrategyEntity


DEFAULT_STRATEGY = {

    "ema_length": 200,

    "rsi_length": 14,

    "adx_length": 14,

    "adx_smoothing": 14,

    "adx_level": 25,

    "oversold": 20,

    "overbought": 80,

    "stop_loss_pips": 300,

    "risk_reward_ratio": 2.0,

}


def initialize_database():

    repos = RepositoryFactory()

    try:

        #
        # Skip if strategies already exist
        #

        existing = repos.strategies.get_all()

        if existing:

            return

        #
        # Create default strategy
        #

        strategy = StrategyEntity(

            name="EMA RSI ADX Default",

            description="Default strategy created automatically.",

            strategy_type="EMA_RSI_ADX",

            config_json=json.dumps(DEFAULT_STRATEGY),

            is_active=True,

        )

        repos.session.add(strategy)

        repos.session.commit()

        print("Default strategy created.")

    finally:

        repos.close()