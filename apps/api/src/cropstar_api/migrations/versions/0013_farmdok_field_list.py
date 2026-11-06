"""Borrowed and missing geometry, and import batches for the farmdok field list

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

import_kind = postgresql.ENUM("farmdok_field_list", name="import_kind")
# Compared as text: a value added to an enum cannot be used in the same transaction.
_KNOWN_GEOMETRY = "(geometry IS NULL) = (geometry_source::text = 'none')"


def upgrade() -> None:
    op.execute("ALTER TYPE area_source ADD VALUE IF NOT EXISTS 'borrowed'")
    op.execute("ALTER TYPE area_source ADD VALUE IF NOT EXISTS 'none'")
    import_kind.create(op.get_bind())
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("harvest_year", sa.SmallInteger(), nullable=False),
        sa.Column("kind", postgresql.ENUM(name="import_kind", create_type=False), nullable=False),
        sa.Column("source_name", sa.String(length=300), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farms.id"],
            name=op.f("fk_import_batches_farm_id_farms"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_import_batches_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batches")),
        sa.UniqueConstraint(
            "farm_id", "harvest_year", "kind", name=op.f("uq_import_batches_farm_id")
        ),
    )
    for table in ("fields", "plots"):
        op.alter_column(table, "geometry", nullable=True)
        op.add_column(table, sa.Column("borrowed_from_year", sa.SmallInteger(), nullable=True))
        op.add_column(table, sa.Column("import_batch_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{table}_import_batch_id_import_batches"),
            table,
            "import_batches",
            ["import_batch_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(op.f(f"ix_{table}_import_batch_id"), table, ["import_batch_id"])
        op.create_check_constraint(
            op.f(f"ck_{table}_geometry_only_when_known"), table, _KNOWN_GEOMETRY
        )


def downgrade() -> None:
    for table in ("fields", "plots"):
        op.drop_constraint(op.f(f"ck_{table}_geometry_only_when_known"), table, type_="check")
        op.drop_index(op.f(f"ix_{table}_import_batch_id"), table_name=table)
        op.drop_constraint(
            op.f(f"fk_{table}_import_batch_id_import_batches"), table, type_="foreignkey"
        )
        op.drop_column(table, "import_batch_id")
        op.drop_column(table, "borrowed_from_year")
    # Areas without geometry cannot survive; their import is gone with the batch table.
    op.execute("DELETE FROM fields WHERE geometry IS NULL")
    op.execute("DELETE FROM plots WHERE geometry IS NULL")
    for table in ("fields", "plots"):
        op.execute(
            f"UPDATE {table} SET geometry_source = 'invekos_open_data' "
            "WHERE geometry_source::text = 'borrowed'"
        )
        op.alter_column(table, "geometry", nullable=False)
    op.drop_table("import_batches")
    import_kind.drop(op.get_bind())
    # Enum values cannot be dropped in place: recreate the type without them.
    op.execute("ALTER TYPE area_source RENAME TO area_source_old")
    postgresql.ENUM("eama_export", "invekos_open_data", name="area_source").create(op.get_bind())
    for table in ("fields", "plots"):
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN geometry_source TYPE area_source "
            "USING geometry_source::text::area_source"
        )
    op.execute("DROP TYPE area_source_old")
