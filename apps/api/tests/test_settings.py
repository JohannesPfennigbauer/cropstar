import pytest

from cropstar_api.settings import Settings


@pytest.mark.parametrize(
    "given",
    [
        "postgres://cropstar:secret@db:5432/cropstar",
        "postgresql://cropstar:secret@db:5432/cropstar",
        "postgresql+psycopg://cropstar:secret@db:5432/cropstar",
    ],
)
def test_database_url_accepts_plain_postgres_urls(given: str) -> None:
    settings = Settings(database_url=given)

    assert settings.database_url == "postgresql+psycopg://cropstar:secret@db:5432/cropstar"


def test_database_url_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROPSTAR_DATABASE_URL", "postgres://u:p@h:5432/d")

    assert Settings().database_url == "postgresql+psycopg://u:p@h:5432/d"
