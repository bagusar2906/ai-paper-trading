

from app.config import StrategyConfig


CATALOG = {

    "EMA_RSI_ADX": {

        "name": "EMA / RSI / ADX",

        "parameters": [

            {
                "name": "ema_length",
                "label": "EMA Length",
                "type": "int",
                "default": StrategyConfig.EMA_LEN,
            },

            {
                "name": "rsi_length",
                "label": "RSI Length",
                "type": "int",
                "default": StrategyConfig.RSI_LEN,
            },

            {
                "name": "adx_length",
                "label": "ADX Length",
                "type": "int",
                "default": StrategyConfig.ADX_LEN,
            },

            {
                "name": "adx_level",
                "label": "ADX Level",
                "type": "int",
                "default": StrategyConfig.ADX_LEVEL,
            },

            {
                "name": "rsi_os",
                "label": "RSI Oversold",
                "type": "int",
                "default": StrategyConfig.RSI_OS,
            },

            {
                "name": "rsi_ob",
                "label": "RSI Overbought",
                "type": "int",
                "default": StrategyConfig.RSI_OB,
            },

            {
                "name": "stop_loss_pips",
                "label": "Stop Loss",
                "type": "int",
                "default": StrategyConfig.STOP_LOSS_PIPS,
            },

            {
                "name": "risk_reward",
                "label": "Risk Reward",
                "type": "float",
                "default": StrategyConfig.RISK_REWARD_RATIO,
            },

        ]

    }

}