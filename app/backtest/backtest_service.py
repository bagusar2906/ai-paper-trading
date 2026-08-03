import json

from app.backtest.backtest_marker import BacktestMarker
from app.backtest.job_manager import job_manager
from app.brokers.paper_broker import PaperBroker
from app.database.base import Base
from app.database.session import create_session_factory
from app.engine.trading_engine import TradingEngine
from app.factories.provider_factory import create_provider
from app.factories.repository_factory import RepositoryFactory
from app.factories.strategy_factory import create_strategy

from .backtest_response import BacktestResponse
from .equity_point import EquityPoint

from app.api.services.statistic_service import StatisticsService
import pandas as pd


class BacktestService:

    def __init__(self):

        pass

    def run(
        self,
        request,
        job_id=None,
    ):

        if job_id:
            self._update_progress(
                job_id,
                5,
                "Downloading history..."
            )

        provider = create_provider()

        try:

            df = provider.get_history(
                request.symbol,
                request.timeframe,
                request.bars,
            )

        finally:

            provider.disconnect()

        
        if job_id:
            self._update_progress(
                job_id,
                20,
                "Preparing strategy..."
            )

        strategy = self._load_strategy(
            request.strategy_id
        )

        df = strategy.prepare(df)

        engine, backtest_session = create_session_factory(
            "sqlite:///:memory:"
        )

        Base.metadata.create_all(engine)

        repos = RepositoryFactory(
            session_factory=backtest_session
        )

        broker = PaperBroker(
            initial_balance=request.initial_balance,
            repos=repos,
        )

        engine = TradingEngine(
            provider=None,
            strategy=strategy,
            broker=broker,
            symbol=request.symbol,
            timeframe=request.timeframe,
            bars=request.bars,
            respect_trading_mode=False,
        )

        #
        # Replay candles
        #
        equity = []

        minimum = strategy.minimum_bars

        
        total = len(df) - minimum

        for index, i in enumerate(range(minimum, len(df))):

            # <<< NEW
            if job_id and index % 20 == 0:

                progress = 20 + int(
                    (index / total) * 70
                )

                self._update_progress(
                    job_id,
                    progress,
                    f"Processing candle {index}/{total}"
                )

            history = df.iloc[: i + 1].copy()

            engine.run_once(history)

            account = broker.get_account()

            equity.append(
                EquityPoint(
                    time=history.iloc[-1].name,
                    equity=account.equity,
                )
            )

        if job_id:
            self._update_progress(
                job_id,
                95,
                "Calculating statistics..."
            )

        trades = broker.get_trades()

        print("===================================")
        print("Trades:", len(trades))

        for trade in trades[:5]:
            print(trade)

        print("===================================")
        
        # Build markers for trades

        markers = []

        for trade in trades:

            markers.append(

                BacktestMarker(

                    time=trade.opened_at,

                    position="belowBar",

                    color="#26a69a",

                    shape="arrowUp",

                    text="BUY",

                )

            )

            

            markers.append(

                BacktestMarker(

                    time=trade.closed_at,

                    position="aboveBar",

                    color="#ef5350",

                    shape="arrowDown",

                    text="SELL",

                )

            )

        #
        # Calculate Maximum Drawdown
        #

        peak = float("-inf")

        max_drawdown = 0

        for point in equity:

            peak = max(
                peak,
                point.equity,
            )

            drawdown = peak - point.equity

            max_drawdown = max(
                max_drawdown,
                drawdown,
            )


        # Build statistics

        statistics = StatisticsService().build(
            trades,
            max_drawdown=max_drawdown
        )

        #
        # Build chart data
        #
        candles = []

        ema = []

        rsi = []

        adx = []

        # Not every strategy produces these columns (Break & Retest is pure
        # price-action, no indicators) - check once instead of assuming they
        # exist, or this crashes with KeyError for any non-EMA/RSI/ADX strategy.
        has_ema = "EMA" in df.columns
        has_rsi = "RSI" in df.columns
        has_adx = "ADX" in df.columns

        for index, row in df.iterrows():

            candles.append({
                "time": index,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
            })

            if has_ema:
                ema.append({
                        "time": index,
                        "value": self._safe_float(row["EMA"]),
                    })

            if has_rsi:
                rsi.append({
                        "time": index,
                        "value": self._safe_float(row["RSI"]),
                    })

            if has_adx:
                adx.append({
                        "time": index,
                        "value": self._safe_float(row["ADX"]),
                    })

        
        if job_id:
            self._update_progress(
                job_id,
                99,
                "Preparing response..."
            )

        return BacktestResponse(
            statistics=statistics,
            equity=equity,
            trades=trades,

            candles=candles,
            ema=ema,
            rsi=rsi,
            adx=adx,
            markers=markers,
        )


    def _load_strategy(self, strategy_id):

        print("Requested strategy_id:", strategy_id)

        repos = RepositoryFactory()

        try:

            entity = repos.strategies.get(strategy_id)

            if entity is None:
                raise Exception(f"Strategy {strategy_id} not found.")

            print("Loaded strategy:", entity.id)
            print("Loaded strategy name:", entity.name)
            print("Loaded config:", entity.config)

            return create_strategy(
                strategy_type=entity.strategy_type,
                config=entity.config,
            )

        finally:

            # Without this, every backtest run permanently leaks one
            # connection from the main app's pool (RepositoryFactory() opens
            # a session against SessionLocal that nothing ever closed) -
            # this is what exhausted the QueuePool and took the trading
            # scheduler down with it.
            repos.close()
    
    def _update_progress(self, job_id, progress, status):

        if job_id:
            job_manager.update(job_id, progress, status)

    def _safe_float(self, value):
        return None if pd.isna(value) else float(value)