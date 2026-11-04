from alembic import command
from sqlalchemy import Engine, create_engine, text

from cropstar_api.db import alembic_config, migrate
from tests.farm_fixtures import Areas, Farm, create


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


def test_migrations_downgrade_and_upgrade_cleanly(database_url: str, engine: Engine) -> None:
    command.downgrade(alembic_config(database_url), "base")
    assert not _postgis_installed(database_url)

    migrate(database_url)
    assert _postgis_installed(database_url)
    # Types were dropped and recreated with new OIDs; pooled connections still cache the old.
    engine.dispose()


def test_migrating_twice_is_a_no_op(database_url: str) -> None:
    migrate(database_url)
    migrate(database_url)
    assert _postgis_installed(database_url)


def test_free_text_details_become_notes_and_back(
    database_url: str, engine: Engine, farm: Farm, areas: Areas
) -> None:
    plan = {"type": "tillage", "implement": "cultivator", "note": "2 cm"}
    task = create(
        farm.worker,
        farm,
        title="Grubbern",
        operation_type="tillage",
        planned_details=plan,
        plot_ids=[areas.plot_2027_a],
    )
    fence = create(farm.worker, farm, title="Zaun", description="Ostseite")

    command.downgrade(alembic_config(database_url), "0010")
    engine.dispose()
    with engine.begin() as connection:
        assert (
            connection.execute(
                text("SELECT planned_details FROM operations WHERE task_id = :id"),
                {"id": task["id"]},
            ).scalar_one()
            == "2 cm"
        )
        connection.execute(
            text("UPDATE operations SET actual_details = 'Grubber, 3 cm' WHERE task_id = :id"),
            {"id": task["id"]},
        )
        connection.execute(
            text("UPDATE tasks SET planned_details = 'Draht mitnehmen' WHERE id = :id"),
            {"id": fence["id"]},
        )

    migrate(database_url)
    engine.dispose()
    with engine.connect() as connection:
        planned, actual = connection.execute(
            text("SELECT planned_details, actual_details FROM operations WHERE task_id = :id"),
            {"id": task["id"]},
        ).one()
        description, fence_plan = connection.execute(
            text("SELECT description, planned_details FROM tasks WHERE id = :id"),
            {"id": fence["id"]},
        ).one()
    assert planned == {"type": "tillage", "note": "2 cm"}
    assert actual == {"type": "tillage", "note": "Grubber, 3 cm"}
    assert (description, fence_plan) == ("Ostseite\n\nDraht mitnehmen", None)
