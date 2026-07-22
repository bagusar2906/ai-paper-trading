from dataclasses import dataclass
from typing import Optional
import logging

import pandas as pd

from app.indicators import ema, rsi, adx_di
from app.config import StrategyConfig, TradingConfig
from app.models.signal import TradingSignal
from app.strategy.base import Strategy

logger = logging.getLogger(__name__)


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
        logger.info("Calculating EMA, RSI and ADX indicators...")  

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
        """
        Mirrors the original TradingView Pine Script logic 1:1:

          BUY:  close > EMA AND ADX > level AND green candle
                AND RSI crosses back above the oversold line this bar
                (RSI[1] < RSI_OS and RSI[0] >= RSI_OS)

          SELL: close < EMA AND ADX > level AND red candle
                AND RSI crosses back below the overbought line this bar
                (RSI[1] > RSI_OB and RSI[0] <= RSI_OB)

        A crossing event (not a static "RSI < 20" / "RSI > 80" threshold)
        is what the indicator actually plots, so we need the previous
        bar's RSI to detect it.
        """

        logger.info(
            "Generating trading signal..."
        )

         # Only calculate indicators if they aren't already present
    #
        if "EMA" not in df.columns:
            df = self.prepare(df)        

        last = df.iloc[-1]

        price = float(last["Close"])

        action = "HOLD"

        reason = "No setup"

        if len(df) >= 2:

            prev = df.iloc[-2]

            is_green = last["Close"] > last["Open"]
            is_red = last["Close"] < last["Open"]

            trend_up = last["Close"] > last["EMA"]
            trend_down = last["Close"] < last["EMA"]

            strong_trend = last["ADX"] > StrategyConfig.ADX_LEVEL

            rsi_crossed_up = (
                prev["RSI"] < StrategyConfig.RSI_OS
                and last["RSI"] >= StrategyConfig.RSI_OS
            )

            rsi_crossed_down = (
                prev["RSI"] > StrategyConfig.RSI_OB
                and last["RSI"] <= StrategyConfig.RSI_OB
            )

            ###################################################
            # BUY
            ###################################################

            if (
                trend_up
                and strong_trend
                and is_green
                and rsi_crossed_up
            ):

                action = "BUY"

                logger.info(
                    "BUY signal generated for %s at price %.5f",
                    symbol,
                    price
                )

                reason = (
                    "Price above EMA, "
                    "ADX strong trend, "
                    "green candle, "
                    "RSI crossed back above oversold"
                )

            ###################################################
            # SELL
            ###################################################

            elif (
                trend_down
                and strong_trend
                and is_red
                and rsi_crossed_down
            ):

                action = "SELL"

                logger.info(
                    "SELL signal generated for %s at price %.5f",
                    symbol,
                    price
                )

                reason = (
                    "Price below EMA, "
                    "ADX strong trend, "
                    "red candle, "
                    "RSI crossed back below overbought"
                )

        ###################################################
        # HOLD
        ###################################################

        stop_loss = None
        take_profit = None

        if action in ("BUY", "SELL"):

            sl_distance = (
                StrategyConfig.STOP_LOSS_PIPS
                * TradingConfig.PIP_SIZE
            )

            tp_distance = sl_distance * StrategyConfig.RISK_REWARD_RATIO

            if action == "BUY":
                stop_loss = price - sl_distance
                take_profit = price + tp_distance
            else:
                stop_loss = price + sl_distance
                take_profit = price - tp_distance

        return TradingSignal(
            symbol=symbol,

            action=action,

            price=price,

            time=df.index[-1],

            ema=float(last["EMA"]),

            rsi=float(last["RSI"]),

            adx=float(last["ADX"]),

            plus_di=float(last["+DI"]),

            minus_di=float(last["-DI"]),

            reason=reason,

            stop_loss=stop_loss,

            take_profit=take_profit,
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