from app.strategy.base import Strategy
from app.strategy.ema_rsi_adx import EMARSIADXStrategy
from app.config import StrategyConfig


def create_strategy() -> Strategy:
    """
    Create the configured trading strategy.
    """

    strategy = StrategyConfig.NAME.lower()

    if strategy == "ema_rsi_adx":
        return EMARSIADXStrategy()

    raise ValueError(f"Unsupported strategy: {StrategyConfig.NAME}")