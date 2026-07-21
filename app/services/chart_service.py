from app.config import TradingConfig
from app.models.chart.candle import Candle
from app.models.chart.chart_position import ChartPosition
from app.models.chart.chart_response import ChartResponse
from app.models.chart.line_series import LinePoint
from app.models.chart.marker import ChartMarker
from app.factories.provider_factory import create_provider
from app.repositories.factory import RepositoryFactory
from app.factories.strategy_factory import create_strategy


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

        df = df.reset_index()

        df = df.rename(
            columns={
                "Time": "time",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
            }
        )

        ema_columns = sorted(
            c
            for c in df.columns
            if c.upper().startswith("EMA")
        )

        fast_ema = ema_columns[0] if len(ema_columns) >= 1 else None
        slow_ema = ema_columns[1] if len(ema_columns) >= 2 else None

        rows = list(df.itertuples(index=False))

        candles = [
            Candle(
                time=row.time,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
            )
            for row in rows
        ]

        ema20 = []

        if fast_ema:

            ema20 = [
                LinePoint(
                    time=row.time,
                    value=getattr(row, fast_ema),
                )
                for row in rows
            ]

        ema50 = []

        if slow_ema:

            ema50 = [
                LinePoint(
                    time=row.time,
                    value=getattr(row, slow_ema),
                )
                for row in rows
            ]

        repos = RepositoryFactory()

        try:

            signals = repos.signals.get_recent(200)

            positions = repos.positions.get_all()

        finally:

            repos.close()

        markers = []

        for signal in signals:

            if signal.action == "BUY":

                markers.append(
                    ChartMarker(
                        time=str(signal.time),
                        position="belowBar",
                        color="#22c55e",
                        shape="arrowUp",
                        text="BUY",
                    )
                )

            elif signal.action == "SELL":

                markers.append(
                    ChartMarker(
                        time=str(signal.time),
                        position="aboveBar",
                        color="#ef4444",
                        shape="arrowDown",
                        text="SELL",
                    )
                )

        chart_positions = [

            ChartPosition(
                symbol=position.symbol,
                side=position.side,
                entry=position.entry_price,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                quantity=position.quantity
            )

            for position in positions

        ]

        return ChartResponse(
            candles=candles,
            ema20=ema20,
            ema50=ema50,
            markers=markers,
            positions=chart_positions,
        )