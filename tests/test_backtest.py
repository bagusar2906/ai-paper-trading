from app.analytics.statistics import TradingStatistics
from app.backtest.backtest_result import BacktestResult
from app.backtest.factory import create_backtest_engine
from app.config import TradingConfig


# =============================================================================
# Normal Backtest
# =============================================================================

def test_backtest_runs():

    engine = create_backtest_engine()

    result = engine.run(
        symbol=TradingConfig.SYMBOL,
        timeframe=TradingConfig.TIMEFRAME,
        bars=500,
    )

    #
    # Result
    #

    assert isinstance(result, BacktestResult)

    assert isinstance(
        result.statistics,
        TradingStatistics,
    )

    #
    # Metadata
    #

    assert result.bars_processed == 500

    assert (
        result.start_balance
        == TradingConfig.INITIAL_BALANCE
    )

    assert result.end_balance > 0

    assert isinstance(result.trades, list)

    #
    # Statistics
    #

    stats = result.statistics

    assert stats.total_trades == len(result.trades)

    assert (
        stats.winning_trades
        + stats.losing_trades
        + stats.breakeven_trades
        == stats.total_trades
    )

    #
    # Balance should equal initial balance plus net profit
    #

    assert result.end_balance == (
        result.start_balance
        + stats.net_profit
    )


# =============================================================================
# Small Dataset
# =============================================================================

def test_backtest_small_dataset():

    engine = create_backtest_engine()

    result = engine.run(
        symbol=TradingConfig.SYMBOL,
        timeframe=TradingConfig.TIMEFRAME,
        bars=50,
    )

    #
    # Result
    #

    assert isinstance(result, BacktestResult)

    assert isinstance(
        result.statistics,
        TradingStatistics,
    )

    #
    # Metadata
    #

    assert result.bars_processed == 50

    assert (
        result.start_balance
        == TradingConfig.INITIAL_BALANCE
    )

    #
    # Strategy should not trade because there are
    # not enough candles to warm up indicators.
    #

    assert len(result.trades) == 0

    assert result.statistics.total_trades == 0

    assert result.statistics.winning_trades == 0

    assert result.statistics.losing_trades == 0

    assert result.statistics.breakeven_trades == 0

    assert result.statistics.net_profit == 0

    #
    # Balance should remain unchanged.
    #

    assert (
        result.end_balance
        == result.start_balance
    )