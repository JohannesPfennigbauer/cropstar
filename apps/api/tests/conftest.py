import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import OperationalError

from cropstar_api.app import create_app
from cropstar_api.db import migrate
from cropstar_api.settings import Settings

TEST_DATABASE_URL = os.environ.get(
    "CROPSTAR_TEST_DATABASE_URL",
    "postgresql+psycopg://cropstar:cropstar@localhost:5432/cropstar_test",
)


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """A freshly created, fully migrated test database, dropped after the session."""
    url = make_url(TEST_DATABASE_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
            connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError as error:
        admin.dispose()
        pytest.fail(
            f"No PostGIS server at {url.render_as_string(hide_password=True)}. "
            f"Start one with `just db-up` or set CROPSTAR_TEST_DATABASE_URL.\n{error}"
        )
    url_string = url.render_as_string(hide_password=False)
    migrate(url_string)
    yield url_string
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def client(database_url: str) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(database_url=database_url))) as test_client:
        yield test_client
