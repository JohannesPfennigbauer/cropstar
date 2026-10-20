from importlib.resources import files

from alembic import command
from alembic.config import Config
from fastapi import Request
from sqlalchemy import Engine, create_engine


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
