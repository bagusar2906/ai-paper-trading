import pandas as pd
import pytest
from types import SimpleNamespace

from app.factories.provider_factory import create_provider
from app.providers.yahoo_provider import YahooProvider
from app.providers.oanda_provider import OandaProvider
from app.providers.twelve_data_provider import TwelveDataProvider
import app.factories.provider_factory as provider_factory


def test_factory_defaults_to_twelve_data(monkeypatch):
    monkeypatch.setattr(provider_factory, "TWELVE_DATA_API_KEY", "test-key")
    monkeypatch.setattr(
        provider_factory,
        "RepositoryFactory",
        lambda: SimpleNamespace(
            settings=SimpleNamespace(
                get_market_data_provider=lambda: "twelve_data"
            ),
            close=lambda: None,
        ),
    )
    provider = create_provider()
    assert isinstance(provider, TwelveDataProvider)
    provider.disconnect()


def test_factory_uses_persisted_market_data_provider(monkeypatch):
    monkeypatch.setattr(
        provider_factory,
        "RepositoryFactory",
        lambda: SimpleNamespace(
            settings=SimpleNamespace(get_market_data_provider=lambda: "yahoo"),
            close=lambda: None,
        ),
    )

    provider = create_provider()

    assert isinstance(provider, YahooProvider)
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


def test_twelve_data_provider_requires_api_key():
    provider = TwelveDataProvider(api_key="")
    with pytest.raises(RuntimeError, match="TWELVE_DATA_API_KEY"):
        provider.connect()


def test_twelve_data_history_uses_completed_candles(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "values": [
                    {"datetime": "2026-10-03 10:00:00", "open": "1", "high": "2", "low": "0.5", "close": "1.5"},
                    {"datetime": "2026-10-03 10:05:00", "open": "1.5", "high": "3", "low": "1", "close": "2"},
                ]
            }

    class Session:
        def get(self, url, params, timeout):
            assert params["symbol"] == "XAU/USD"
            assert params["interval"] == "5min"
            assert params["outputsize"] == 2
            return Response()

    monkeypatch.setattr(
        "app.providers.twelve_data_provider.pd.Timestamp.now",
        classmethod(lambda cls, tz=None: pd.Timestamp("2026-10-03 10:05:30", tz=tz)),
    )
    provider = TwelveDataProvider(api_key="key", session=Session())
    provider.connect()
    df = provider.get_history("XAUUSD", "M5", 1)

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 1
    assert df.index[-1] == pd.Timestamp("2026-10-03 10:00:00", tz="UTC")


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


def test_yahoo_provider_uses_application_cache_directory(monkeypatch, tmp_path):
    configured_paths = []
    monkeypatch.setattr(
        "app.providers.yahoo_provider.YAHOO_CACHE_DIRECTORY",
        tmp_path / "yfinance",
    )
    monkeypatch.setattr(
        "app.providers.yahoo_provider.yf.set_tz_cache_location",
        configured_paths.append,
    )

    provider = YahooProvider()
    provider.connect()

    assert configured_paths == [str((tmp_path / "yfinance").resolve())]
    assert provider.is_connected()


def test_yahoo_history_exposes_provider_errors(monkeypatch):
    class FailingTicker:
        def history(self, period, interval):
            raise OSError("cache is unavailable")

    monkeypatch.setattr(
        "app.providers.yahoo_provider.yf.Ticker",
        lambda symbol: FailingTicker(),
    )
    provider = YahooProvider()
    provider.connect()

    with pytest.raises(RuntimeError, match="Yahoo Finance request failed"):
        provider.get_history("XAUUSD", "M5", 10)

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
        provider.get_history("XAUUSD", "bad-timeframe", 5)

    provider.disconnect()
