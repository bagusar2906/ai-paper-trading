from app.database.database import init_database


def initialize():

    init_database()

    # later:
    # configure_logging()
    # load_env()
    # validate_config()