from dataclasses import asdict
from fastapi import APIRouter

from app.repositories.factory import RepositoryFactory

router = APIRouter()

repos = RepositoryFactory()


@router.get("/dashboard")
def dashboard():

    account = repos.accounts.get()

    if account is None:
        return {
            "account": None
        }

    return {
        "account": asdict(account),
    }