import json
import logging

import pandas as pd

from app.api.services.statistic_service import StatisticsService
from app.backtest.backtest_marker import BacktestMarker
from app.backtest.candidate_acceptance_gate import CandidateAcceptanceGate
from app.backtest.job_manager import job_manager
from app.brokers.paper_broker import PaperBroker
from app.database.base import Base
from app.database.session import create_session_factory
from app.engine.trading_engine import TradingEngine
from app.factories.provider_factory import create_provider
from app.factories.repository_factory import RepositoryFactory
from app.factories.strategy_factory import create_strategy
from app.features.core_v1 import FEATURE_SET_ID
from app.labels.future_return import FutureReturnLabel
from app.ml.inference import RegisteredModelPredictor
from app.strategy.ai_assisted_xgb import AIAssistedXGBStrategy

from .backtest_response import BacktestResponse
from .equity_point import EquityPoint


logger = logging.getLogger(__name__)


class BacktestService:
    """Runs paper-only strategy replays and isolated candidate comparisons."""

    def run(self, request, job_id=None):
        self._update_progress(job_id, 5, "Downloading history...")
        provider = create_provider()
        try:
            history = provider.get_history(request.symbol, request.timeframe, request.bars)
        finally:
            provider.disconnect()

        if request.candidate_model_id:
            return self._run_candidate_comparison(request, history, job_id)

        self._update_progress(job_id, 20, "Preparing strategy...")
        strategy = self._load_strategy(request.strategy_id)
        return self._run_strategy(request, history, strategy, job_id)

    def _run_candidate_comparison(self, request, history, job_id):
        strategy_type, config = self._load_strategy_definition(request.strategy_id)
        if strategy_type.upper() != "AI_ASSISTED_XGB":
            raise ValueError("candidate comparison is only available for AI Assisted XGBoost")

        candidate, champion, evaluation_start = self._comparison_models(
            request.candidate_model_id, request.symbol, request.timeframe, config
        )
        evaluation_history = self._out_of_sample_history(history, evaluation_start)
        self._update_progress(job_id, 20, "Running candidate on its held-out window...")
        candidate_strategy = AIAssistedXGBStrategy(
            config, predictor=RegisteredModelPredictor(candidate.model_id, {"candidate"})
        )
        candidate_report = self._run_strategy(
            request, evaluation_history, candidate_strategy, job_id, 20, 55
        )
        if candidate_report.stopped:
            candidate_report.comparison = {
                "status": "stopped",
                "candidate_model_id": candidate.model_id,
                "champion_model_id": champion.model_id,
                "evaluation_start": evaluation_start.isoformat(),
            }
            return candidate_report

        self._update_progress(job_id, 56, "Running champion on the same held-out window...")
        champion_strategy = AIAssistedXGBStrategy(
            config, predictor=RegisteredModelPredictor(champion.model_id, {"champion"})
        )
        champion_report = self._run_strategy(
            request, evaluation_history, champion_strategy, job_id, 56, 95
        )
        candidate_report.comparison = {
            "status": "completed",
            "candidate_model_id": candidate.model_id,
            "champion_model_id": champion.model_id,
            "evaluation_start": evaluation_start.isoformat(),
            "candidate": candidate_report.statistics,
            "champion": champion_report.statistics,
            "same_history": True,
            "paper_only": True,
            "acceptance_gate": CandidateAcceptanceGate().evaluate(
                candidate_report.statistics, champion_report.statistics
            ),
        }
        return candidate_report

    def _comparison_models(self, candidate_model_id, symbol, timeframe, config):
        label_id = FutureReturnLabel(
            int(config.get("horizon_candles", 12)),
            float(config.get("up_return_threshold", 0.003)),
        ).definition_id
        repos = RepositoryFactory()
        try:
            candidate = repos.model_registry.get(candidate_model_id)
            if candidate is None or candidate.status != "candidate":
                raise ValueError("select a registered candidate model; champions and retired models cannot be compared here")
            if candidate.feature_set_id != FEATURE_SET_ID or candidate.label_definition_id != label_id:
                raise ValueError("candidate feature set or label does not match the selected AI Assisted XGBoost strategy")
            metadata = self._decode_metadata(candidate.metadata_json)
            context = metadata.get("market_context")
            window = metadata.get("evaluation_window")
            if not isinstance(context, dict) or not isinstance(window, dict) or not window.get("start_time"):
                raise ValueError("candidate has no recorded market context/out-of-sample window; retrain it before comparison")
            if context.get("symbol", "").upper() != symbol.upper() or context.get("timeframe", "").upper() != timeframe.upper():
                raise ValueError("candidate was trained for a different symbol or timeframe")
            champion = repos.model_registry.get_champion(FEATURE_SET_ID, label_id)
            if champion is None:
                raise ValueError("no compatible champion is available for comparison")
            evaluation_start = pd.Timestamp(window["start_time"])
            if evaluation_start.tzinfo is None:
                evaluation_start = evaluation_start.tz_localize("UTC")
            return candidate, champion, evaluation_start
        finally:
            repos.close()

    @staticmethod
    def _decode_metadata(value):
        try:
            data = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _out_of_sample_history(history, evaluation_start):
        if history.index.tz is None:
            evaluation_start = evaluation_start.tz_localize(None)
        selected = history.loc[history.index >= evaluation_start].copy()
        if selected.empty:
            raise ValueError("the requested history does not include the candidate's held-out evaluation window")
        return selected

    def _run_strategy(self, request, history, strategy, job_id, progress_start=20, progress_end=90):
        df = strategy.prepare(history)
        engine, backtest_session = create_session_factory("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        repos = RepositoryFactory(session_factory=backtest_session)
        broker = PaperBroker(initial_balance=request.initial_balance, repos=repos)
        trading_engine = TradingEngine(
            provider=None, strategy=strategy, broker=broker, symbol=request.symbol,
            timeframe=request.timeframe, bars=request.bars, respect_trading_mode=False,
        )

        equity, stopped = [], False
        total = len(df) - strategy.minimum_bars
        if total <= 0:
            raise ValueError(f"Not enough held-out history for this strategy; need more than {strategy.minimum_bars} bars.")
        start_backtest = getattr(strategy, "start_backtest", None)
        end_backtest = getattr(strategy, "end_backtest", None)
        if start_backtest:
            start_backtest()
        try:
            for number, end in enumerate(range(strategy.minimum_bars, len(df)), start=1):
                if job_id and job_manager.is_cancel_requested(job_id):
                    stopped = True
                    break
                if job_id and number % 5 == 0:
                    progress = progress_start + int((number / total) * (progress_end - progress_start))
                    self._update_progress(job_id, min(progress, progress_end), f"Processing candle {number}/{total}")
                candle_history = df.iloc[: end + 1].copy()
                trading_engine.run_once(candle_history)
                account = broker.get_account()
                equity.append(EquityPoint(time=candle_history.iloc[-1].name, equity=account.equity))
        finally:
            if end_backtest:
                end_backtest()

        trades = broker.get_trades()
        statistics = StatisticsService().build(trades, max_drawdown=self._maximum_drawdown(equity))
        return self._response(df, statistics, equity, trades, stopped)

    @staticmethod
    def _maximum_drawdown(equity):
        peak, maximum = float("-inf"), 0.0
        for point in equity:
            peak = max(peak, point.equity)
            maximum = max(maximum, peak - point.equity)
        return maximum

    def _response(self, df, statistics, equity, trades, stopped):
        markers = []
        for trade in trades:
            markers.extend((
                BacktestMarker(time=trade.opened_at, position="belowBar", color="#26a69a", shape="arrowUp", text="BUY"),
                BacktestMarker(time=trade.closed_at, position="aboveBar", color="#ef5350", shape="arrowDown", text="SELL"),
            ))
        candles, ema, rsi, adx = [], [], [], []
        for index, row in df.iterrows():
            candles.append({"time": index, "open": float(row["Open"]), "high": float(row["High"]), "low": float(row["Low"]), "close": float(row["Close"])})
            if "EMA" in df.columns:
                ema.append({"time": index, "value": self._safe_float(row["EMA"])})
            if "RSI" in df.columns:
                rsi.append({"time": index, "value": self._safe_float(row["RSI"])})
            if "ADX" in df.columns:
                adx.append({"time": index, "value": self._safe_float(row["ADX"])})
        return BacktestResponse(statistics, equity, trades, candles, ema, rsi, adx, markers, stopped)

    def _load_strategy(self, strategy_id):
        strategy_type, config = self._load_strategy_definition(strategy_id)
        return create_strategy(strategy_type=strategy_type, config=config)

    @staticmethod
    def _load_strategy_definition(strategy_id):
        repos = RepositoryFactory()
        try:
            entity = repos.strategies.get(strategy_id)
            if entity is None:
                raise ValueError(f"Strategy {strategy_id} not found.")
            return entity.strategy_type, dict(entity.config or {})
        finally:
            repos.close()

    @staticmethod
    def _update_progress(job_id, progress, status):
        if job_id:
            job_manager.update(job_id, progress, status)

    @staticmethod
    def _safe_float(value):
        return None if pd.isna(value) else float(value)
