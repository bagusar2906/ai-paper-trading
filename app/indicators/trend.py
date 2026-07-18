import pandas as pd

def ema(series: pd.Series, length: int):
    return series.ewm(span=length, adjust=False).mean()