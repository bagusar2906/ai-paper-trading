from dataclasses import dataclass

from app.models.chart.candle import Candle
from app.models.chart.line_series import LinePoint
from app.models.chart.marker import ChartMarker


@dataclass
class ChartResponse:

    candles: list[Candle]

    ema20: list[LinePoint]

    ema50: list[LinePoint]

    markers: list[ChartMarker]