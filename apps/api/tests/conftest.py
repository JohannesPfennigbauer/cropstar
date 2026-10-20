import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from cropstar_api.app import create_app
from cropstar_api.auth.mailer import Email
from cropstar_api.db import migrate
from cropstar_api.models import Base
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


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _empty_tables(request: pytest.FixtureRequest) -> Iterator[None]:
    """Tests that touch the database each start from empty tables."""
    if "database_url" not in request.fixturenames:
        yield
        return
    engine: Engine = request.getfixturevalue("engine")
    yield
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} CASCADE"))


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session, session.begin():
        yield session


class RecordingMailer:
    """Stands in for SMTP: keeps every email instead of sending it."""

    def __init__(self) -> None:
        self.sent: list[Email] = []

    @property
    def available(self) -> bool:
        return True

    def send(self, email: Email) -> None:
        self.sent.append(email)


@pytest.fixture
def mailer() -> RecordingMailer:
    return RecordingMailer()


@pytest.fixture
def settings(database_url: str) -> Settings:
    # The test client talks plain http, where browsers would drop Secure cookies.
    return Settings(
        database_url=database_url, cookie_secure=False, public_base_url="https://cropstar.test"
    )


@pytest.fixture
def client(settings: Settings, mailer: RecordingMailer) -> Iterator[TestClient]:
    with TestClient(create_app(settings, mailer=mailer)) as test_client:
        yield test_client


@pytest.fixture
def client_without_email(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
