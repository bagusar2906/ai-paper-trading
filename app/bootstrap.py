from app.database.database import init_database
from app.logging_config import configure_logging


def initialize():

    configure_logging()
    init_database()
