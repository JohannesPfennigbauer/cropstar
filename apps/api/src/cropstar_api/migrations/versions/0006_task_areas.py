"""Task areas

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_fields",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("field_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["field_id"],
            ["fields.id"],
            name=op.f("fk_task_fields_field_id_fields"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_task_fields_task_id_tasks"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("task_id", "field_id", name=op.f("pk_task_fields")),
    )
    op.create_index(op.f("ix_task_fields_field_id"), "task_fields", ["field_id"], unique=False)
    op.create_table(
        "task_plots",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("plot_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plot_id"], ["plots.id"], name=op.f("fk_task_plots_plot_id_plots"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_task_plots_task_id_tasks"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("task_id", "plot_id", name=op.f("pk_task_plots")),
    )
    op.create_index(op.f("ix_task_plots_plot_id"), "task_plots", ["plot_id"], unique=False)
    op.add_column("tasks", sa.Column("harvest_year", sa.SmallInteger(), nullable=True))
    op.create_index("ix_tasks_farm_id_harvest_year", "tasks", ["farm_id", "harvest_year"])


def downgrade() -> None:
    op.drop_index("ix_tasks_farm_id_harvest_year", table_name="tasks")
    op.drop_column("tasks", "harvest_year")
    op.drop_index(op.f("ix_task_plots_plot_id"), table_name="task_plots")
    op.drop_table("task_plots")
    op.drop_index(op.f("ix_task_fields_field_id"), table_name="task_fields")
    op.drop_table("task_fields")
