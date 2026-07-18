from app.engine.base import Engine
from app.engine.result import EngineResult


class TradingEngine(Engine):

    def __init__(
        self,
        provider,
        strategy,
        broker,
        symbol,
        timeframe,
        bars=300,
    ):
        self.provider = provider
        self.strategy = strategy
        self.broker = broker

        self.symbol = symbol
        self.timeframe = timeframe
        self.bars = bars

    def run_once(self):

        df = self.provider.get_history(
            self.symbol,
            self.timeframe,
            self.bars,
        )

        if not self.strategy.can_run(df):

            return EngineResult(
                account=self.broker.get_account(),
                message="Not enough data",
            )

        df = self.strategy.prepare(df)

        signal = self.strategy.generate_signal(
            self.symbol,
            df,
        )

        if signal is not None:

            self.broker.execute(signal)

        positions = self.broker.get_positions()

        return EngineResult(
            signal=signal,
            position=positions[-1] if positions else None,
            account=self.broker.get_account(),
            message="Completed",
        )