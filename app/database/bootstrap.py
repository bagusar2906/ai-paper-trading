from app.config import TradingConfig
from app.database import Base, engine, SessionLocal
from app.database.models import AccountEntity


def init_database():

    Base.metadata.create_all(bind=engine)

    session = SessionLocal()

    try:

        account = session.query(AccountEntity).first()

        if account is None:

            session.add(
                AccountEntity(
                    balance=TradingConfig.INITIAL_BALANCE,
                    equity=TradingConfig.INITIAL_BALANCE,
                    margin=0,
                    free_margin=TradingConfig.INITIAL_BALANCE,
                    floating_pnl=0,
                )
            )

            session.commit()

    finally:

        session.close()