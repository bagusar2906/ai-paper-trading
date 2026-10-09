from app.database.models import PositionEntity
from app.repositories.base_repository import BaseRepository, commit_or_flush


class PositionRepository(BaseRepository):

    def add(self, position):

        self.session.add(position)
        commit_or_flush(self.session)

    def remove(self, position):

        self.session.delete(position)
        commit_or_flush(self.session)

    def get_all(self):

        return self.session.query(PositionEntity).all()

    def get_by_symbol(self, symbol):

        return (
            self.session
            .query(PositionEntity)
            .filter_by(symbol=symbol)
            .first()
        )

    def get_by_id(self, position_id: int):

        return self.session.get(PositionEntity, position_id)
    
    def update(self, position):

        commit_or_flush(self.session)