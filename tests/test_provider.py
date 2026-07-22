import pandas as pd
import pytest

from app.factories.provider_factory import create_provider
from app.providers.yahoo_provider import YahooProvider
from app.providers.oanda_provider import OandaProvider


def test_factory_defaults_to_config_provider():
    provider = create_provider()
    assert isinstance(provider, YahooProvider)  # config.DATA_PROVIDER == "yahoo"
    provider.disconnect()


def test_factory_accepts_explicit_provider_name():
    provider = create_provider("yahoo")
    assert isinstance(provider, YahooProvider)
    provider.disconnect()


def test_factory_raises_on_unknown_provider():
    with pytest.raises(ValueError):
        create_provider("not_a_real_provider")


def test_oanda_provider_requires_api_key():
    provider = OandaProvider(api_key="")
    with pytest.raises(RuntimeError):
        provider.connect()


def test_yahoo_get_history_returns_expected_columns(monkeypatch):
    """Mocks the yfinance call so this test doesn't need real network access."""
    idx = pd.date_range("2026-01-01", periods=10, freq="5min")
    fake_df = pd.DataFrame(
        {
            "Open": range(10),
            "High": range(10),
            "Low": range(10),
            "Close": range(10),
            "Volume": range(10),
        },
        index=idx,
    )

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, period, interval):
            return fake_df

    monkeypatch.setattr(
        "app.providers.yahoo_provider.yf.Ticker", FakeTicker
    )

    provider = YahooProvider()
    provider.connect()
    df = provider.get_history("XAUUSD", "M5", 5)

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 5  # tail(bars) applied
    provider.disconnect()


def test_yahoo_get_history_rejects_mt_style_timeframe(monkeypatch):
    """Regression test: the backtest dashboard used to submit MetaTrader-style
    labels ('M15', 'H1', ...) instead of the app's own '15m' / '1h' format.
    _INTERVAL_MAP.get(timeframe, timeframe) used to silently fall back to
    passing the raw (invalid) string straight to yfinance as the interval,
    which yfinance quietly interpreted as "no data" instead of erroring.
    Unrecognized timeframes must now fail fast and clearly instead."""

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError(
            "yfinance should never be called with an unrecognized timeframe"
        )

    monkeypatch.setattr(
        "app.providers.yahoo_provider.yf.Ticker", _should_not_be_called
    )

    provider = YahooProvider()
    provider.connect()

    with pytest.raises(ValueError):
        provider.get_history("XAUUSD", "M15", 5)

    provider.disconnect()
