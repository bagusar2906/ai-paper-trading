import json

from app.database import SessionLocal
from app.database.models import StrategyProfileEntity


class StrategyProfileService:

    def get_all(self):

        session = SessionLocal()

        try:

            return (
                session
                .query(StrategyProfileEntity)
                .order_by(StrategyProfileEntity.name)
                .all()
            )

        finally:

            session.close()

    def get(self, profile_id):

        session = SessionLocal()

        try:

            return (
                session
                .query(StrategyProfileEntity)
                .filter(
                    StrategyProfileEntity.id == profile_id
                )
                .first()
            )

        finally:

            session.close()

    def create(
        self,
        name,
        strategy,
        parameters,
    ):

        session = SessionLocal()

        try:

            profile = StrategyProfileEntity(

                name=name,

                strategy=strategy,

                parameters_json=json.dumps(parameters),

            )

            session.add(profile)

            session.commit()

            session.refresh(profile)

            return profile

        finally:

            session.close()

    def update(
        self,
        profile_id,
        parameters,
    ):

        session = SessionLocal()

        try:

            profile = (
                session.query(StrategyProfileEntity)
                .filter(
                    StrategyProfileEntity.id == profile_id
                )
                .first()
            )

            if profile is None:
                return None

            profile.parameters_json = json.dumps(parameters)

            session.commit()

            session.refresh(profile)

            return profile

        finally:

            session.close()

    def delete(
        self,
        profile_id,
    ):

        session = SessionLocal()

        try:

            profile = (
                session.query(StrategyProfileEntity)
                .filter(
                    StrategyProfileEntity.id == profile_id
                )
                .first()
            )

            if profile is None:
                return False

            session.delete(profile)

            session.commit()

            return True

        finally:

            session.close()