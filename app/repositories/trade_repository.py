from app.database.models import TradeEntity
from app.repositories.base_repository import BaseRepository, commit_or_flush


class TradeRepository(BaseRepository):

    def add(self, trade):

        self.session.add(trade)
        commit_or_flush(self.session)

    def get_all(self):

        return self.session.query(TradeEntity).all()