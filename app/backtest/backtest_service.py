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

    def run(
        self,
        request,
        job_id=None,
    ):

        # <<< NEW
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

        # <<< NEW
        if job_id:
            self._update_progress(
                job_id,
                20,
                "Preparing strategy..."
            )

        strategy = create_strategy()

        #
        # Calculate indicators once
        #
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

        # <<< NEW
        if job_id:
            self._update_progress(
                job_id,
                95,
                "Calculating statistics..."
            )

        trades = broker.get_trades()

        statistics = StatisticsService().build(
            trades
        )

        #
        # Build chart data
        #
        candles = []

        ema = []

        rsi = []

        adx = []

        for index, row in df.iterrows():

            candles.append({
                "time": index,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
            })

            ema.append({
                    "time": index,
                    "value": self._safe_float(row["EMA"]),
                })

            rsi.append({
                    "time": index,
                    "value": self._safe_float(row["RSI"]),
                })

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
        )
    
    def _update_progress(self, job_id, progress, status):

        if job_id:
            job_manager.update(job_id, progress, status)

    def _safe_float(self, value):
        return None if pd.isna(value) else float(value)