from dataclasses import dataclass
from typing import Optional

import pandas as pd

from app.indicators import ema, rsi, adx_di
from app.config import StrategyConfig
from app.models.signal import TradingSignal
from app.strategy.base import Strategy


class EMARSIADXStrategy(Strategy):

    def __init__(
        self,
        ema_length=StrategyConfig.EMA_LEN,
        rsi_length=StrategyConfig.RSI_LEN,
        adx_length=StrategyConfig.ADX_LEN,
        adx_smoothing=StrategyConfig.ADX_SMOOTH,
    ):

        self.ema_length = ema_length
        self.rsi_length = rsi_length
        self.adx_length = adx_length
        self.adx_smoothing = adx_smoothing

    @property
    def name(self) -> str:
        return "EMA/RSI/ADX"

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all indicators.
        """

        df = df.copy()

        df["EMA"] = ema(df["Close"], self.ema_length)

        df["RSI"] = rsi(df["Close"], self.rsi_length)

        df["+DI"], df["-DI"], df["ADX"] = adx_di(
            df,
            self.adx_length,
            self.adx_smoothing,
        )

        return df

    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
    ) -> TradingSignal:

        df = self.prepare(df)

        last = df.iloc[-1]

        price = float(last["Close"])

        action = "HOLD"

        reason = "No setup"

        ###################################################
        # BUY
        ###################################################

        if (
            last["Close"] > last["EMA"]
            and last["RSI"] < StrategyConfig.RSI_OS
            and last["ADX"] > StrategyConfig.ADX_LEVEL
            and last["+DI"] > last["-DI"]
        ):

            action = "BUY"

            reason = (
                "Price above EMA, "
                "RSI oversold, "
                "ADX strong trend"
            )

        ###################################################
        # SELL
        ###################################################

        elif (
            last["Close"] < last["EMA"]
            and last["RSI"] > StrategyConfig.RSI_OB
            and last["ADX"] > StrategyConfig.ADX_LEVEL
            and last["-DI"] > last["+DI"]
        ):

            action = "SELL"

            reason = (
                "Price below EMA, "
                "RSI overbought, "
                "ADX strong trend"
            )

        ###################################################
        # HOLD
        ###################################################

        return TradingSignal(
            symbol=symbol,

            action=action,

            price=price,

            time=str(df.index[-1]),

            ema=float(last["EMA"]),

            rsi=float(last["RSI"]),

            adx=float(last["ADX"]),

            plus_di=float(last["+DI"]),

            minus_di=float(last["-DI"]),

            reason=reason,
        )

    def generate_dataframe(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Return dataframe with indicators.
        Useful for plotting and backtesting.
        """

        return self.prepare(df)