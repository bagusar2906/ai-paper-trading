from app.database.models import StrategyEntity
from app.repositories.base_repository import BaseRepository


class StrategyRepository(BaseRepository):

    def get_all(self):

        return self.session.query(
            StrategyEntity
        ).all()

    def get(self, strategy_id: int):

        return (
            self.session
            .query(StrategyEntity)
            .filter(
                StrategyEntity.id == strategy_id
            )
            .first()
        )

    def add(self, entity):

        self.session.add(entity)
        self.session.commit()

        return entity

    def update(self):

        self.session.commit()

    def delete(self, entity):

        self.session.delete(entity)
        self.session.commit()

    def get_active(self):

        return (

            self.session

            .query(StrategyEntity)

            .filter(
                StrategyEntity.is_active == True
            )

            .first()

        )