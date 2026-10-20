from alembic import command
from sqlalchemy import create_engine, text

from cropstar_api.db import alembic_config, migrate


def _postgis_installed(database_url: str) -> bool:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return bool(
                connection.execute(
                    text("SELECT count(*) FROM pg_extension WHERE extname = 'postgis'")
                ).scalar_one()
            )
    finally:
        engine.dispose()


def test_migrations_downgrade_and_upgrade_cleanly(database_url: str) -> None:
    command.downgrade(alembic_config(database_url), "base")
    assert not _postgis_installed(database_url)

    migrate(database_url)
    assert _postgis_installed(database_url)


def test_migrating_twice_is_a_no_op(database_url: str) -> None:
    migrate(database_url)
    migrate(database_url)
    assert _postgis_installed(database_url)
