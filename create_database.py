from app.database import Base
from app.database import engine

# IMPORTANT
import app.database.models


def main():

    Base.metadata.create_all(bind=engine)

    print("Database created successfully.")


if __name__ == "__main__":
    main()