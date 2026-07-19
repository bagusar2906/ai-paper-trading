from dataclasses import dataclass, field

from app.models.chart.candle import Candle
from app.models.chart.chart_position import ChartPosition
from app.models.chart.line_series import LinePoint
from app.models.chart.marker import ChartMarker


@dataclass
class ChartResponse:

    candles: list[Candle]

    ema20: list[LinePoint]

    ema50: list[LinePoint]

    markers: list[ChartMarker] = field(default_factory=list)

    positions: list[ChartPosition] = field(default_factory=list)