from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """Future persistence models register here for Alembic."""


class Database:
    def __init__(self, url: str) -> None:
        self.engine: Engine = create_engine(
            url, pool_pre_ping=True, connect_args={"connect_timeout": 3}
        )
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def check(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def close(self) -> None:
        self.engine.dispose()
