from dataclasses import dataclass
from datetime import datetime
import pandas as pd


@dataclass
class MarketEvent:

    symbol: str

    timeframe: str

    closed_time: datetime

    dataframe: pd.DataFrame