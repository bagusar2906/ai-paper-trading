import numpy as np
import pandas as pd

from app import worker
from app.models.signal import TradingSignal


def test_worker_run_returns_trading_signal(monkeypatch):
    rng = np.random.default_rng(1)
    n = 60
    close = 2000 + np.cumsum(rng.normal(0, 1, n))
    idx = pd.date_range("2026-01-01", periods=n, freq="5min")
    fake_df = pd.DataFrame(
        {
            "Open": close,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": rng.uniform(100, 1000, n),
        },
        index=idx,
    )

    class FakeProvider:
        def get_history(self, symbol, timeframe, bars):
            return fake_df

        def disconnect(self):
            self.disconnected = True

    fake_provider = FakeProvider()
    monkeypatch.setattr(
        worker, "create_provider", lambda name=None: fake_provider
    )

    signal = worker.run(provider_name="yahoo", bars=n)

    assert isinstance(signal, TradingSignal)
    assert signal.action in {"BUY", "SELL", "HOLD"}
