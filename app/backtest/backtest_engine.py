class BacktestEngine:

    def __init__(
        self,
        engine,
        provider,
        tracker,
    ):
        self.engine = engine
        self.provider = provider
        self.tracker = tracker

    def run(
        self,
        symbol,
        timeframe,
        bars,
    ):

        history = self.provider.get_history(
            symbol,
            timeframe,
            bars,
        )

        warmup = self.engine.bars

        for i in range(warmup, len(history)):

            df = history.iloc[: i + 1]

            self.engine.run_once(df)

        return self.tracker.calculate(
            self.engine.broker.get_trades()
        )