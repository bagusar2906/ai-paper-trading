import json

from app.database.models import StrategyEntity
from app.models.strategy import Strategy
from app.repositories.base_repository import BaseRepository


class StrategyRepository(BaseRepository):

    def _to_model(self, entity: StrategyEntity) -> Strategy:

        config = self._decode_config(entity.config_json)

        # Convert JSON string into dict
        if isinstance(config, str):
            config = json.loads(config)

        return Strategy(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            strategy_type=entity.strategy_type,
            config=config,
            is_active=entity.is_active,
        )

    def _decode_config(self, value):

        while isinstance(value, str):
            value = json.loads(value)

        return value
     
    def get_all(self):

        entities = (
            self.session
            .query(StrategyEntity)
            .all()
        )

        return [
            self._to_model(entity)
            for entity in entities
        ]

    def get(self, strategy_id: int):

        entity = (
            self.session
            .query(StrategyEntity)
            .filter(
                StrategyEntity.id == strategy_id
            )
            .first()
        )

        if entity is None:
            return None

        return self._to_model(entity)

    def add(self, strategy: Strategy):

        entity = StrategyEntity(

            name=strategy.name,

            description=strategy.description,

            strategy_type=strategy.strategy_type,

            # Convert dict -> JSON string
            config_json=json.dumps(strategy.config),

            is_active=strategy.is_active,

        )

        self.session.add(entity)

        self.session.commit()

        self.session.refresh(entity)

        return self._to_model(entity)

    def update(self, strategy: Strategy):

        entity = (
            self.session
            .query(StrategyEntity)
            .filter(
                StrategyEntity.id == strategy.id
            )
            .first()
        )

        if entity is None:
            return None

        entity.name = strategy.name
        entity.description = strategy.description
        entity.strategy_type = strategy.strategy_type

        # Convert dict -> JSON string
        entity.config_json = json.dumps(strategy.config)

        entity.is_active = strategy.is_active

        self.session.commit()

        return self._to_model(entity)

    def delete(self, strategy: Strategy):

        entity = (
            self.session
            .query(StrategyEntity)
            .filter(
                StrategyEntity.id == strategy.id
            )
            .first()
        )

        if entity:

            self.session.delete(entity)

            self.session.commit()


    def set_active(self, strategy_id: int):

        self.session.query(StrategyEntity).update(
            {
                StrategyEntity.is_active: False
            }
        )

        entity = (
            self.session.query(StrategyEntity)
            .filter(StrategyEntity.id == strategy_id)
            .first()
        )

        if entity is None:
            self.session.rollback()
            return None

        entity.is_active = True

        self.session.commit()

        return self._to_model(entity)


    def get_active(self):

        entity = (

            self.session

            .query(StrategyEntity)

            .filter(
                StrategyEntity.is_active == True
            )

            .first()

        )

        if entity is None:
            return None

        return self._to_model(entity)