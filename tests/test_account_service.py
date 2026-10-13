import pytest

from app.models.account import Account
from app.services.account_service import AccountService


def test_adjust_funds_updates_balance_equity_and_free_margin(monkeypatch):
    account = Account(
        balance=10_000,
        equity=10_100,
        margin=0,
        free_margin=10_100,
        floating_pnl=100,
    )

    class Accounts:
        def get(self):
            return account

        def update(self, updated):
            assert updated is account

    class Repos:
        accounts = Accounts()

        def close(self):
            pass

    monkeypatch.setattr(
        "app.services.account_service.RepositoryFactory",
        lambda: Repos(),
    )

    updated = AccountService().adjust_funds(500)

    assert updated.balance == 10_500
    assert updated.equity == 10_600
    assert updated.free_margin == 10_600


def test_adjust_funds_rejects_withdrawal_beyond_free_margin(monkeypatch):
    account = Account(100, 100, 0, 25, 0)

    class Repos:
        accounts = type("Accounts", (), {"get": lambda self: account})()

        def close(self):
            pass

    monkeypatch.setattr(
        "app.services.account_service.RepositoryFactory",
        lambda: Repos(),
    )

    with pytest.raises(ValueError, match="free margin"):
        AccountService().adjust_funds(-50)
