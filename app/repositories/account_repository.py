from app.database.models import AccountEntity
from app.models.account import Account
from app.repositories.base_repository import BaseRepository


class AccountRepository(BaseRepository):

    def get(self):

        entity = self.session.query(AccountEntity).first()

        if entity is None:
            return None

        return Account(
            balance=entity.balance,
            equity=entity.equity,
            margin=entity.margin,
            free_margin=entity.free_margin,
            floating_pnl=entity.floating_pnl,
        )

    def add(self, account: Account):

        entity = AccountEntity(
            balance=account.balance,
            equity=account.equity,
            margin=account.margin,
            free_margin=account.free_margin,
            floating_pnl=account.floating_pnl,
        )

        self.session.add(entity)
        self.session.commit()

    def update(self, account: Account):

        entity = self.session.query(AccountEntity).first()

        entity.balance = account.balance
        entity.equity = account.equity
        entity.margin = account.margin
        entity.free_margin = account.free_margin
        entity.floating_pnl = account.floating_pnl

        self.session.commit()