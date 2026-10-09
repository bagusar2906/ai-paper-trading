from app.config import TradingConfig
from app.factories.provider_factory import create_provider
from app.factories.strategy_factory import create_strategy
from app.factories.strategy_loader import load_active_strategy


class SignalService:

    HISTORY_BARS = 300

    def __init__(self):

        self.provider = create_provider()
        self.strategy = load_active_strategy()
        self.context_broker = None
        if hasattr(self.strategy, "bind_broker"):
            from app.brokers.paper_broker import PaperBroker
            self.context_broker = PaperBroker()
            self.strategy.bind_broker(self.context_broker)

    def generate(self):

        df = self.provider.get_history(
            TradingConfig.SYMBOL,
            getattr(self.strategy, "required_timeframe", TradingConfig.TIMEFRAME),
            max(self.HISTORY_BARS, self.strategy.minimum_bars + 1),
        )

        if getattr(self.strategy, "required_timeframe", None):
            import pandas as pd
            from app.services.training_data_sync_service import TrainingDataSyncService
            df = TrainingDataSyncService._normalize(df, pd.Timedelta(hours=1), pd.Timestamp.now(tz="UTC"))
            if df.empty:
                raise ValueError("No completed H1 candles available")

        return self.strategy.generate_signal(
            TradingConfig.SYMBOL,
            df,
        )

    def close(self):

        self.provider.disconnect()
        if self.context_broker is not None:
            self.context_broker.close()
