from collections.abc import Iterator
from importlib.resources import files
from typing import Annotated

from alembic import command
from alembic.config import Config
from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session


def create_db_engine(database_url: str) -> Engine:
    # Fail fast instead of hanging when the database host is unreachable.
    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(files("cropstar_api") / "migrations"))
    # Passed as an attribute, not an ini option, so a `%` in the password survives.
    config.attributes["database_url"] = database_url
    return config


def migrate(database_url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)


def get_engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


def _transaction(engine: Annotated[Engine, Depends(get_engine)]) -> Iterator[Session]:
    """One transaction per request: committed if the endpoint returns, rolled back if it raises."""
    with Session(engine, expire_on_commit=False) as session, session.begin():
        yield session


# Function scope commits before the response is sent, so a client never sees success for
# work that failed to commit.
Db = Annotated[Session, Depends(_transaction, scope="function")]
