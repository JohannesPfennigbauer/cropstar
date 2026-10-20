"""Operations

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operation_types",
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_operation_types")),
    )
    # The global list of Operation Types; names live in the UI's translations.
    op.bulk_insert(
        sa.table(
            "operation_types", sa.column("code", sa.String), sa.column("position", sa.SmallInteger)
        ),
        [
            {"code": "tillage", "position": 1},
            {"code": "sowing", "position": 2},
            {"code": "fertilisation", "position": 3},
            {"code": "harvest", "position": 4},
        ],
    )
    op.create_table(
        "operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("plot_id", sa.Uuid(), nullable=False),
        # Same Status as Tasks; the type exists already.
        sa.Column("status", postgresql.ENUM(name="task_status", create_type=False), nullable=False),
        sa.Column("planned_details", sa.Text(), nullable=True),
        sa.Column("actual_details", sa.Text(), nullable=True),
        sa.Column("performed_on", sa.Date(), nullable=True),
        sa.Column("completed_by_id", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["completed_by_id"],
            ["users.id"],
            name=op.f("fk_operations_completed_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["plot_id"], ["plots.id"], name=op.f("fk_operations_plot_id_plots"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_operations_task_id_tasks"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operations")),
        sa.UniqueConstraint("task_id", "plot_id", name=op.f("uq_operations_task_id")),
    )
    op.create_index(op.f("ix_operations_plot_id"), "operations", ["plot_id"], unique=False)
    op.add_column("tasks", sa.Column("operation_type", sa.String(length=30), nullable=True))
    op.add_column("tasks", sa.Column("planned_details", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_tasks_operation_type_operation_types"),
        "tasks",
        "operation_types",
        ["operation_type"],
        ["code"],
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_tasks_operation_type_operation_types"), "tasks", type_="foreignkey")
    op.drop_column("tasks", "planned_details")
    op.drop_column("tasks", "operation_type")
    op.drop_index(op.f("ix_operations_plot_id"), table_name="operations")
    op.drop_table("operations")
    op.drop_table("operation_types")
