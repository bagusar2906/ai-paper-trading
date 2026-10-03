from datetime import datetime, timezone

import pandas as pd
import pytest

from app.backtest.costs import BacktestCostAssumptions
from app.backtest.metrics import maximum_drawdown, sharpe_ratio
from app.backtest.equity_point import EquityPoint
from app.brokers.cost_aware_backtest_broker import CostAwareBacktestBroker
from app.engine.trading_engine import TradingEngine
from app.enums.signal_action import SignalAction
from app.models.signal import TradingSignal
from app.strategy.base import Strategy


def _signal(action=SignalAction.BUY, quantity=2.0):
    return TradingSignal(
        symbol="XAUUSD",
        action=action,
        price=100.0,
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        quantity=quantity,
        stop_loss=95.0,
        take_profit=110.0,
    )


def test_cost_aware_broker_defers_fill_until_next_candle_open():
    broker = CostAwareBacktestBroker(
        assumptions=BacktestCostAssumptions(
            spread_price=0.2,
            slippage_price=0.05,
            commission_per_unit_per_side=0.25,
        )
    )
    broker.execute(_signal())
    assert broker.get_positions() == []

    broker.advance_candle("XAUUSD", 101.0, datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc))
    position = broker.get_positions()[0]
    assert position.entry_price == pytest.approx(101.15)

    trade = broker.close_position("XAUUSD", 105.0)
    assert trade.exit_price == pytest.approx(104.85)
    assert trade.pnl == pytest.approx(6.4)
    assert broker.get_account().balance == pytest.approx(10006.4)
    costs = broker.get_cost_breakdown()
    assert costs.spread_cost == pytest.approx(0.4)
    assert costs.slippage_cost == pytest.approx(0.2)
    assert costs.commission_cost == pytest.approx(1.0)
    assert costs.total_cost == pytest.approx(1.6)


class _BuyStrategy(Strategy):
    @property
    def name(self):
        return "test"

    @classmethod
    def schema(cls):
        return []

    @property
    def minimum_bars(self):
        return 2

    def prepare(self, df):
        return df

    def generate_signal(self, symbol, df):
        price = float(df.iloc[-1]["Close"])
        return TradingSignal(
            symbol=symbol,
            action=SignalAction.BUY,
            price=price,
            time=df.index[-1],
            stop_loss=price - 1,
            take_profit=price + 10,
        )


def _engine_candles():
    index = pd.date_range("2026-01-01", periods=3, freq="5min", tz="UTC")
    return pd.DataFrame({
        "Open": [100.0, 101.0, 102.0],
        "High": [101.0, 102.0, 103.0],
        "Low": [99.0, 100.0, 101.0],
        "Close": [100.5, 101.5, 102.5],
        "Volume": [1.0, 1.0, 1.0],
    }, index=index)


def test_trading_engine_fills_backtest_signal_on_following_candle_open():
    broker = CostAwareBacktestBroker()
    engine = TradingEngine(
        provider=None,
        strategy=_BuyStrategy(),
        broker=broker,
        symbol="XAUUSD",
        timeframe="M5",
        respect_trading_mode=False,
    )
    candles = _engine_candles()
    engine.run_once(candles.iloc[:2])
    assert broker.get_positions() == []
    assert len(broker.pending_signals) == 1

    engine.run_once(candles)
    position = broker.get_positions()[0]
    assert position.entry_price == pytest.approx(102.0)
    assert position.opened_at == candles.index[-1]


def test_backtest_metrics_report_drawdown_and_documented_sharpe_inputs():
    equity = [
        EquityPoint(time=datetime(2026, 1, 1, tzinfo=timezone.utc), equity=100.0),
        EquityPoint(time=datetime(2026, 1, 2, tzinfo=timezone.utc), equity=110.0),
        EquityPoint(time=datetime(2026, 1, 3, tzinfo=timezone.utc), equity=99.0),
        EquityPoint(time=datetime(2026, 1, 4, tzinfo=timezone.utc), equity=105.0),
    ]
    assert maximum_drawdown(equity) == pytest.approx(11.0)
    assert sharpe_ratio(equity, periods_per_year=252) != 0.0


def test_cost_assumptions_reject_unsupported_or_negative_values():
    with pytest.raises(ValueError, match="next_candle_open"):
        BacktestCostAssumptions(fill_timing="current_candle_close")
    with pytest.raises(ValueError, match="cannot be negative"):
        BacktestCostAssumptions(spread_price=-0.1)
