from importlib.metadata import version
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from cropstar_api.db import get_engine

router = APIRouter(tags=["status"])


class Liveness(BaseModel):
    status: Literal["ok"]
    service: Literal["cropstar-api"]


class DatabaseStatus(BaseModel):
    reachable: bool
    postgres_version: str | None
    postgis_version: str | None


class ApiStatus(BaseModel):
    service: Literal["cropstar-api"]
    version: str
    database: DatabaseStatus


@router.get("/healthz", operation_id="getLiveness")
def read_liveness() -> Liveness:
    """Liveness probe for the container orchestrator; intentionally does no I/O."""
    return Liveness(status="ok", service="cropstar-api")


@router.get("/status", operation_id="getStatus")
def read_status(engine: Annotated[Engine, Depends(get_engine)]) -> ApiStatus:
    """Report whether the database is reachable and which PostgreSQL and PostGIS it runs."""
    return ApiStatus(
        service="cropstar-api",
        version=version("cropstar-api"),
        database=_database_status(engine),
    )


def _database_status(engine: Engine) -> DatabaseStatus:
    try:
        with engine.connect() as connection:
            postgres_version = connection.execute(text("SHOW server_version")).scalar_one()
            postgis_version = connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'postgis'")
            ).scalar_one_or_none()
    except SQLAlchemyError:
        return DatabaseStatus(reachable=False, postgres_version=None, postgis_version=None)
    return DatabaseStatus(
        reachable=True, postgres_version=postgres_version, postgis_version=postgis_version
    )
