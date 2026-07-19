from app.database.models import AccountEntity
from app.repositories.base_repository import BaseRepository


class AccountRepository(BaseRepository):

    def get(self):

        return self.session.query(AccountEntity).first()

    def add(self, account):

        self.session.add(account)
        self.session.commit()

    def update(self):

        self.session.commit()