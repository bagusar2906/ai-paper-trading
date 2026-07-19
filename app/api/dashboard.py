from dataclasses import asdict
from fastapi import APIRouter

from app.repositories.factory import RepositoryFactory

router = APIRouter()

repos = RepositoryFactory()


@router.get("/dashboard")
def dashboard():

    account = repos.accounts.get()

    positions = repos.positions.get_all()

    trades = repos.trades.get_all()

    signals = repos.signals.get_recent(20)

    return {
        "account": asdict(account),
        "positions": [asdict(p) for p in positions],
        "trades": [asdict(t) for t in trades],
        "signals": [asdict(s) for s in signals],
    }