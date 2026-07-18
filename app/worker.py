from app.providers.factory import create_provider
from app.strategy import EMARSIADXStrategy
from app.config import TradingConfig


def run(provider_name="yahoo", bars=500):
    provider = create_provider(provider_name)
    strategy = EMARSIADXStrategy()

    try:
        df = provider.get_history(TradingConfig.SYMBOL, TradingConfig.TIMEFRAME, bars)
        signal = strategy.generate_signal(TradingConfig.SYMBOL, df)
        print(signal)
        return signal
    finally:
        provider.disconnect()


if __name__ == "__main__":
    run()
