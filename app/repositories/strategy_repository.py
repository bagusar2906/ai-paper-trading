import json

from app.database.models import StrategyEntity
from app.models.strategy import Strategy
from app.repositories.base_repository import BaseRepository


class StrategyRepository(BaseRepository):

    def get(self, strategy_id):

        entity = (
            self.session.query(StrategyEntity)
            .filter(
                StrategyEntity.id == strategy_id
            )
            .first()
        )

        if entity is None:

            return None

        return Strategy(

            id=entity.id,

            name=entity.name,

            description=entity.description,

            strategy_type=entity.strategy_type,

            config=json.loads(
                entity.config_json
            ),

        )

    def get_all(self):

        entities = (
            self.session.query(
                StrategyEntity
            )
            .all()
        )

        return [

            Strategy(

                id=e.id,

                name=e.name,

                description=e.description,

                strategy_type=e.strategy_type,

                config=json.loads(
                    e.config_json
                ),

            )

            for e in entities

        ]

    def add(self, strategy: Strategy):

        entity = StrategyEntity(

            name=strategy.name,

            description=strategy.description,

            strategy_type=strategy.strategy_type,

            config_json=json.dumps(
                strategy.config
            ),

        )

        self.session.add(entity)

        self.session.commit()

        strategy.id = entity.id

        return strategy

    def update(self, strategy: Strategy):

        entity = (
            self.session.query(StrategyEntity)
            .filter(
                StrategyEntity.id == strategy.id
            )
            .first()
        )

        entity.name = strategy.name
        entity.description = strategy.description
        entity.strategy_type = strategy.strategy_type
        entity.config_json = json.dumps(
            strategy.config
        )

        self.session.commit()

    def delete(self, strategy_id):

        entity = (
            self.session.query(StrategyEntity)
            .filter(
                StrategyEntity.id == strategy_id
            )
            .first()
        )

        if entity:

            self.session.delete(entity)

            self.session.commit()