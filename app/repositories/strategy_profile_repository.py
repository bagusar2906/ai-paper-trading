import json

from sqlalchemy.orm import Session

from app.database.models import StrategyProfileEntity



class StrategyProfileRepository:

    def __init__(self, session: Session):

        self.session = session

    #
    # List all profiles
    #
    def get_all(self):

        return (
            self.session
            .query(StrategyProfileEntity)
            .order_by(StrategyProfileEntity.name)
            .all()
        )

    #
    # Get one profile
    #
    def get(self, profile_id: int):

        return (
            self.session
            .query(StrategyProfileEntity)
            .filter(
                StrategyProfileEntity.id == profile_id
            )
            .first()
        )

    #
    # Create profile
    #
    def create(
        self,
        name: str,
        strategy: str,
        parameters: dict,
    ):

        entity = StrategyProfileEntity(

            name=name,

            strategy=strategy,

            parameters_json=json.dumps(parameters),

        )

        self.session.add(entity)

        self.session.commit()

        self.session.refresh(entity)

        return entity

    #
    # Update profile
    #
    def update(
        self,
        profile_id: int,
        parameters: dict,
    ):

        entity = self.get(profile_id)

        if entity is None:
            return None

        entity.parameters_json = json.dumps(parameters)

        self.session.commit()

        return entity

    #
    # Delete profile
    #
    def delete(
        self,
        profile_id: int,
    ):

        entity = self.get(profile_id)

        if entity is None:
            return False

        self.session.delete(entity)

        self.session.commit()

        return True