from app.strategy.base import Strategy
from app.strategy.ema_rsi_adx import EMARSIADXStrategy
from app.strategy.break_retest import BreakRetestStrategy
from app.strategy.ai_agent import AIAgentStrategy
from app.strategy.ai_assisted_xgb import AIAssistedXGBStrategy


def create_strategy(
    strategy_type: str,
    config: dict,
) -> Strategy:

    strategy_type = strategy_type.upper()

    if strategy_type == "EMA_RSI_ADX":

        return EMARSIADXStrategy(config)

    if strategy_type == "BREAK_RETEST":

        return BreakRetestStrategy(config)

    if strategy_type == "AI_AGENT":

        return AIAgentStrategy(config)

    if strategy_type == "AI_ASSISTED_XGB":

        return AIAssistedXGBStrategy(config)

    raise ValueError(
        f"Unsupported strategy: {strategy_type}"
    )


def get_strategy_schema(
    strategy_type: str,
):

    strategy_type = strategy_type.upper()

    if strategy_type == "EMA_RSI_ADX":

        return EMARSIADXStrategy.schema()

    if strategy_type == "BREAK_RETEST":

        return BreakRetestStrategy.schema()

    if strategy_type == "AI_AGENT":

        return AIAgentStrategy.schema()

    if strategy_type == "AI_ASSISTED_XGB":

        return AIAssistedXGBStrategy.schema()

    raise ValueError(
        f"Unsupported strategy: {strategy_type}"
    )


def get_supported_strategies():

    return [

        {
            "value": "EMA_RSI_ADX",
            "label": "EMA + RSI + ADX",
        },

        {
            "value": "BREAK_RETEST",
            "label": "Break & Retest",
        },

        {
            "value": "AI_AGENT",
            "label": "AI Agent (OpenAI)",
        },

        {
            "value": "AI_ASSISTED_XGB",
            "label": "AI Assisted XGBoost (Paper Only)",
        },

    ]
