from app.strategy.base import Strategy
from app.strategy.ema_rsi_adx import EMARSIADXStrategy


def create_strategy(
    strategy_type: str,
    config: dict,
) -> Strategy:

    strategy_type = strategy_type.upper()

    if strategy_type == "EMA_RSI_ADX":

        return EMARSIADXStrategy(config)

    raise ValueError(
        f"Unsupported strategy: {strategy_type}"
    )


def get_strategy_schema(
    strategy_type: str,
):

    strategy_type = strategy_type.upper()

    if strategy_type == "EMA_RSI_ADX":

        return EMARSIADXStrategy.schema()

    raise ValueError(
        f"Unsupported strategy: {strategy_type}"
    )


def get_supported_strategies():

    return [

        {
            "value": "EMA_RSI_ADX",
            "label": "EMA + RSI + ADX",
        },

    ]