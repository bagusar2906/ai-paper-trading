from app.strategy.base import Strategy
from app.strategy.ema_rsi_adx import EMARSIADXStrategy


def create_strategy(
    strategy_type: str,
    config: dict,
) -> Strategy:

    strategy_type = strategy_type.upper()

    if strategy_type == "EMA_RSI_ADX":

        return EMARSIADXStrategy(
            config
        )

    raise ValueError(
        f"Unsupported strategy: {strategy_type}"
    )