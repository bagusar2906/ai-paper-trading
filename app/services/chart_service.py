from dataclasses import asdict

from app.config import TradingConfig
from app.models.chart.candle import Candle
from app.models.chart.chart_response import ChartResponse
from app.models.chart.line_series import LinePoint
from app.models.chart.marker import ChartMarker
from app.providers.factory import create_provider
from app.strategy.factory import create_strategy


class ChartService:

    HISTORY = 300

    def get_chart(self):

        provider = create_provider()

        try:

            df = provider.get_history(
                TradingConfig.SYMBOL,
                TradingConfig.TIMEFRAME,
                self.HISTORY,
            )

        finally:

            provider.disconnect()

        strategy = create_strategy()

        df = strategy.prepare(df)

        # Convert index into a normal column
        df = df.reset_index()

        # Normalize OHLC names
        df = df.rename(
            columns={
                "Time": "time",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
            }
        )

        # Find EMA columns automatically
        ema_columns = [
            c for c in df.columns
            if c.upper().startswith("EMA")
        ]

        ema_columns.sort()

        if len(ema_columns) >= 2:
            fast_ema = ema_columns[0]
            slow_ema = ema_columns[1]
        else:
            fast_ema = None
            slow_ema = None

        candles = [
            Candle(
                time=row.time,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
            )
            for row in df.itertuples(index=False)
        ]

        ema_fast = []

        if fast_ema:
            ema_fast = [
                LinePoint(
                    time=row.time,
                    value=getattr(row, fast_ema),
                )
                for row in df.itertuples(index=False)
            ]

        ema_slow = []

        if slow_ema:
            ema_slow = [
                LinePoint(
                    time=row.time,
                    value=getattr(row, slow_ema),
                )
                for row in df.itertuples(index=False)
            ]

        return ChartResponse(
            candles=candles,
            ema20=ema_fast,
            ema50=ema_slow,
            markers=[],
        )