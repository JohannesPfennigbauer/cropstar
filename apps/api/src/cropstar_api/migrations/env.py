from typing import Any

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import create_engine, pool

from cropstar_api.models import Base
from cropstar_api.settings import Settings

config = context.config
database_url: str = config.attributes.get("database_url") or Settings().database_url


def include_object(
    obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    # Leave tables we do not model alone, e.g. PostGIS's spatial_ref_sys.
    if type_ == "table" and reflected and compare_to is None:
        return False
    return bool(alembic_helpers.include_object(obj, name, type_, reflected, compare_to))  # type: ignore[no-untyped-call]


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=Base.metadata,
        include_object=include_object,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            include_object=include_object,
            process_revision_directives=alembic_helpers.writer,
            render_item=alembic_helpers.render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
