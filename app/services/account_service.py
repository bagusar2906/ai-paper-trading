import math

from app.config import TradingConfig
from app.factories.repository_factory import RepositoryFactory
from app.models.account import Account


class AccountService:

    def adjust_funds(self, amount: float) -> Account:

        if not math.isfinite(amount) or amount == 0:
            raise ValueError("Fund adjustment must be a non-zero number.")

        repos = RepositoryFactory()

        try:
            account = repos.accounts.get()

            if account is None:
                account = Account(
                    balance=TradingConfig.INITIAL_BALANCE,
                    equity=TradingConfig.INITIAL_BALANCE,
                    margin=0.0,
                    free_margin=TradingConfig.INITIAL_BALANCE,
                    floating_pnl=0.0,
                )
                repos.accounts.add(account)

            if account.balance + amount < 0:
                raise ValueError("Withdrawal cannot make the balance negative.")

            if account.free_margin + amount < 0:
                raise ValueError("Withdrawal exceeds available free margin.")

            account.balance += amount
            account.equity += amount
            account.free_margin += amount

            repos.accounts.update(account)

            return account

        finally:
            repos.close()
