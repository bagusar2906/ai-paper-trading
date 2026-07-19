from app.database.models import TradeEntity
from app.repositories.base_repository import BaseRepository


class TradeRepository(BaseRepository):

    def add(self, trade):

        self.session.add(trade)
        self.session.commit()

    def get_all(self):

        return self.session.query(TradeEntity).all()