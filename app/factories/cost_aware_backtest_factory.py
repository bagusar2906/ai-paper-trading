"""Factory for the isolated, cost-aware baseline backtest path."""

from app.analytics.performance_tracker import PerformanceTracker
from app.backtest.backtest_engine import BacktestEngine
from app.backtest.costs import BacktestCostAssumptions
from app.brokers.cost_aware_backtest_broker import CostAwareBacktestBroker
from app.config import TradingConfig
from app.engine.trading_engine import TradingEngine
from app.factories.provider_factory import create_provider
from app.factories.strategy_loader import load_active_strategy


def create_cost_aware_backtest_engine(
    assumptions: BacktestCostAssumptions,
    *,
    periods_per_year: int,
):
    """Build a paper-only backtest with next-open fills and explicit costs."""
    provider = create_provider()
    strategy = load_active_strategy()
    broker = CostAwareBacktestBroker(
        initial_balance=TradingConfig.INITIAL_BALANCE,
        assumptions=assumptions,
    )
    broker.periods_per_year = periods_per_year
    engine = TradingEngine(
        provider,
        strategy,
        broker,
        TradingConfig.SYMBOL,
        TradingConfig.TIMEFRAME,
    )
    return BacktestEngine(engine, provider, PerformanceTracker())
