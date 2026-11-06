"""farmdok crop production log: imported Tasks and remembered assignments

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

term_kind = postgresql.ENUM("crop", "activity", "product", name="farmdok_term_kind")


def upgrade() -> None:
    op.execute("ALTER TYPE import_kind ADD VALUE IF NOT EXISTS 'farmdok_crop_log'")
    op.add_column("tasks", sa.Column("import_batch_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_tasks_import_batch_id_import_batches"),
        "tasks",
        "import_batches",
        ["import_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_tasks_import_batch_id"), "tasks", ["import_batch_id"])

    term_kind.create(op.get_bind())
    op.create_table(
        "farmdok_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind", postgresql.ENUM(name="farmdok_term_kind", create_type=False), nullable=False
        ),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("land_use_code", sa.String(length=10), nullable=True),
        sa.Column("operation_type", sa.String(length=30), nullable=True),
        sa.Column("farm_input_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farms.id"],
            name=op.f("fk_farmdok_assignments_farm_id_farms"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["operation_type"],
            ["operation_types.code"],
            name=op.f("fk_farmdok_assignments_operation_type_operation_types"),
        ),
        sa.ForeignKeyConstraint(
            ["farm_input_id"],
            ["farm_inputs.id"],
            name=op.f("fk_farmdok_assignments_farm_input_id_farm_inputs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_farmdok_assignments")),
        sa.UniqueConstraint("farm_id", "kind", "name", name=op.f("uq_farmdok_assignments_farm_id")),
    )


def downgrade() -> None:
    op.drop_table("farmdok_assignments")
    term_kind.drop(op.get_bind())
    op.drop_index(op.f("ix_tasks_import_batch_id"), table_name="tasks")
    op.drop_constraint(op.f("fk_tasks_import_batch_id_import_batches"), "tasks", type_="foreignkey")
    op.drop_column("tasks", "import_batch_id")
    # Batches of the removed kind go first, then the type is rebuilt without the value.
    op.execute("DELETE FROM import_batches WHERE kind::text = 'farmdok_crop_log'")
    op.execute("ALTER TYPE import_kind RENAME TO import_kind_old")
    postgresql.ENUM("farmdok_field_list", name="import_kind").create(op.get_bind())
    op.execute(
        "ALTER TABLE import_batches ALTER COLUMN kind TYPE import_kind "
        "USING kind::text::import_kind"
    )
    op.execute("DROP TYPE import_kind_old")
