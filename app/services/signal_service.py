from app.config import TradingConfig
from app.factories.provider_factory import create_provider
from app.factories.strategy_factory import create_strategy
from app.factories.strategy_loader import load_active_strategy


class SignalService:

    HISTORY_BARS = 300

    def __init__(self):

        self.provider = create_provider()
        self.strategy = load_active_strategy()

    def generate(self):

        df = self.provider.get_history(
            TradingConfig.SYMBOL,
            TradingConfig.TIMEFRAME,
            self.HISTORY_BARS,
        )

        return self.strategy.generate_signal(
            TradingConfig.SYMBOL,
            df,
        )

    def close(self):

        self.provider.disconnect()