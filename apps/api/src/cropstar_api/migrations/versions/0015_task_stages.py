"""Task stages: each Farm's own steps before a Task is done

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-08
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# As in `models.DEFAULT_TASK_STAGES`, copied so this migration never changes.
_DEFAULTS = ("Geplant", "Offen", "In Arbeit")
# Existing Open Tasks were simply "open": they go to that stage.
_EXISTING = "Offen"


def upgrade() -> None:
    op.create_table(
        "task_stages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farms.id"], name=op.f("fk_task_stages_farm_id_farms"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_stages")),
    )
    op.create_index("ix_task_stages_farm_id_position", "task_stages", ["farm_id", "position"])
    op.add_column("tasks", sa.Column("stage_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_tasks_stage_id_task_stages"),
        "tasks",
        "task_stages",
        ["stage_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_tasks_stage_id"), "tasks", ["stage_id"])

    connection = op.get_bind()
    stages = sa.table(
        "task_stages",
        sa.column("id", sa.Uuid()),
        sa.column("farm_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("position", sa.SmallInteger()),
    )
    for (farm_id,) in connection.execute(sa.text("SELECT id FROM farms")):
        ids = {name: uuid.uuid4() for name in _DEFAULTS}
        connection.execute(
            stages.insert(),
            [
                {"id": ids[name], "farm_id": farm_id, "name": name, "position": index}
                for index, name in enumerate(_DEFAULTS)
            ],
        )
        connection.execute(
            sa.text("UPDATE tasks SET stage_id = :stage WHERE farm_id = :farm"),
            {"stage": ids[_EXISTING], "farm": farm_id},
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_tasks_stage_id"), table_name="tasks")
    op.drop_constraint(op.f("fk_tasks_stage_id_task_stages"), "tasks", type_="foreignkey")
    op.drop_column("tasks", "stage_id")
    op.drop_table("task_stages")
