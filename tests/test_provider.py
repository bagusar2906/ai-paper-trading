import pandas as pd
import pytest

from app.providers.factory import create_provider
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
    df = provider.get_history("XAUUSD", "5m", 5)

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 5  # tail(bars) applied
    provider.disconnect()
