from app.database.models import SignalEntity
from app.repositories.base_repository import BaseRepository


class SignalRepository(BaseRepository):

    def add(self, signal):

        self.session.add(signal)
        self.session.commit()

    def get_all(self):

        return self.session.query(SignalEntity).all()