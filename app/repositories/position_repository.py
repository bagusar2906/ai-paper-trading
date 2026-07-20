from app.database.models import PositionEntity
from app.repositories.base_repository import BaseRepository


class PositionRepository(BaseRepository):

    def add(self, position):

        self.session.add(position)
        self.session.commit()

    def remove(self, position):

        self.session.delete(position)
        self.session.commit()

    def get_all(self):

        return self.session.query(PositionEntity).all()

    def get_by_symbol(self, symbol):

        return (
            self.session
            .query(PositionEntity)
            .filter_by(symbol=symbol)
            .first()
        )

    def update(self, position):

        self.session.commit()