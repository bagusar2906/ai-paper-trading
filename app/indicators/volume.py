import numpy as np
import pandas as pd


def obv(close, volume):

    direction = np.sign(close.diff().fillna(0))

    return (direction * volume.fillna(0)).cumsum()


def cmf(df, length=20):

    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    volume = df["Volume"]

    mf_mult = (
        ((close - low) - (high - close))
        / (high - low).replace(0, np.nan)
    )

    mf_vol = mf_mult * volume

    return (
        mf_vol.rolling(length).sum()
        / volume.rolling(length).sum()
    )


def relative_volume(volume, length=20):

    return volume / volume.rolling(length).mean()