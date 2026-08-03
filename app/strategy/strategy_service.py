from app.models.strategy import Strategy


class StrategyService:

    def __init__(self, repos):
        self.repos = repos

    def get_all(self):
        return self.repos.strategies.get_all()

    def get(self, strategy_id):
        return self.repos.strategies.get(strategy_id)

    def create(self, request):

        strategy = Strategy(
            name=request.name,
            description=request.description,
            strategy_type=request.strategy_type,
            config=request.config,
            is_active=False,
        )

        return self.repos.strategies.add(strategy)

    def update(self, strategy_id, request):

        strategy = self.repos.strategies.get(strategy_id)

        if strategy is None:
            return None

        strategy.name = request.name
        strategy.description = request.description
        strategy.strategy_type = request.strategy_type
        strategy.config = request.config

        return self.repos.strategies.update(strategy)

    def delete(self, strategy_id):

        strategy = self.repos.strategies.get(strategy_id)

        if strategy is None:
            return False

        self.repos.strategies.delete(strategy)

        return True

    def set_active(self, strategy_id):

        return self.repos.strategies.set_active(strategy_id)