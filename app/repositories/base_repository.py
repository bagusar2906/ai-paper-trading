from sqlalchemy.orm import Session


def commit_or_flush(session):
    """Keep candle writes inside the recovery transaction when one is active."""
    if session.info.get("paper_trading_transaction"):
        session.flush()
    else:
        session.commit()


class BaseRepository:

    def __init__(self, session: Session):
        self.session = session
