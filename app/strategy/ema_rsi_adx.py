from typing import Optional
import logging

import pandas as pd

from app.indicators import ema, rsi, adx_di
from app.config import TradingConfig
from app.models.signal import TradingSignal
from app.strategy.base import Strategy

logger = logging.getLogger(__name__)


class EMARSIADXStrategy(Strategy):

    def __init__(
        self,
        config: dict,
    ):

        super().__init__()

        #
        # Strategy Parameters
        #

        self.ema_length = config["ema_length"]

        self.rsi_length = config["rsi_length"]

        self.adx_length = config["adx_length"]

        self.adx_level = config["adx_level"]

        self.oversold = config["oversold"]

        self.overbought = config["overbought"]

        #
        # Optional parameters
        #

        self.adx_smoothing = config.get(
            "adx_smoothing",
            self.adx_length,
        )

        self.stop_loss_pips = config.get(
            "stop_loss_pips",
            300,
        )

        self.risk_reward_ratio = config.get(
            "risk_reward_ratio",
            2.0,
        )

    @property
    def name(self):

        return "EMA/RSI/ADX"

    @property
    def minimum_bars(self):

        return max(
            self.ema_length,
            self.rsi_length,
            self.adx_length,
        )

    def prepare(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        logger.info(
            "Preparing indicators..."
        )

        df = df.copy()

        df["EMA"] = ema(
            df["Close"],
            self.ema_length,
        )

        df["RSI"] = rsi(
            df["Close"],
            self.rsi_length,
        )

        (
            df["+DI"],
            df["-DI"],
            df["ADX"],
        ) = adx_di(

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

        if "EMA" not in df.columns:

            df = self.prepare(df)

        last = df.iloc[-1]

        price = float(last["Close"])

        action = "HOLD"

        reason = "No setup"

        stop_loss = None

        take_profit = None

        if len(df) >= 2:

            prev = df.iloc[-2]

            is_green = last["Close"] > last["Open"]

            is_red = last["Close"] < last["Open"]

            trend_up = last["Close"] > last["EMA"]

            trend_down = last["Close"] < last["EMA"]

            strong_trend = (

                last["ADX"]

                > self.adx_level

            )

            rsi_crossed_up = (

                prev["RSI"] < self.oversold

                and

                last["RSI"] >= self.oversold

            )

            rsi_crossed_down = (

                prev["RSI"] > self.overbought

                and

                last["RSI"] <= self.overbought

            )

            #
            # BUY
            #

            if (

                trend_up

                and strong_trend

                and is_green

                and rsi_crossed_up

            ):

                action = "BUY"

                reason = (

                    "Price above EMA, "

                    "ADX strong trend, "

                    "RSI crossed above oversold"

                )

            #
            # SELL
            #

            elif (

                trend_down

                and strong_trend

                and is_red

                and rsi_crossed_down

            ):

                action = "SELL"

                reason = (

                    "Price below EMA, "

                    "ADX strong trend, "

                    "RSI crossed below overbought"

                )

        #
        # SL / TP
        #

        if action in ("BUY", "SELL"):

            sl_distance = (

                self.stop_loss_pips

                * TradingConfig.PIP_SIZE

            )

            tp_distance = (

                sl_distance

                * self.risk_reward_ratio

            )

            if action == "BUY":

                stop_loss = (

                    price - sl_distance

                )

                take_profit = (

                    price + tp_distance

                )

            else:

                stop_loss = (

                    price + sl_distance

                )

                take_profit = (

                    price - tp_distance

                )

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

        return self.prepare(df)