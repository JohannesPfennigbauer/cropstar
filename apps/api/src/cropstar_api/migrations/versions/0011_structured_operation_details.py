"""Structured Planned and Actual Details, and the Operation Types of M1

The free-text details become notes inside the structured details of their Operation Type.
Text planned for a Task without an Operation Type moves into its description. Downgrading
keeps the notes as text; structured values entered since are lost.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TYPES = (
    "tillage",
    "mechanical_weed_control",
    "mulching",
    "sowing",
    "fertilisation",
    "harvest",
)
_NEW_TYPES = ("mechanical_weed_control", "mulching")
_OLD_POSITIONS = {"tillage": 1, "sowing": 2, "fertilisation": 3, "harvest": 4}
_COLUMNS = (
    ("tasks", "planned_details"),
    ("operations", "planned_details"),
    ("operations", "actual_details"),
)


_operation_types = sa.table(
    "operation_types", sa.column("code", sa.String), sa.column("position", sa.SmallInteger)
)


def upgrade() -> None:
    op.bulk_insert(
        _operation_types,
        [{"code": code, "position": 100 + i} for i, code in enumerate(_NEW_TYPES)],
    )
    for position, code in enumerate(_TYPES, start=1):
        _set_position(code, position)

    op.execute(
        """
        UPDATE tasks
        SET description = concat_ws(E'\\n\\n', description, planned_details),
            planned_details = NULL
        WHERE operation_type IS NULL AND planned_details IS NOT NULL
        """
    )
    for table, column in _COLUMNS:
        op.add_column(table, sa.Column(f"{column}_new", postgresql.JSONB()))
    op.execute(
        """
        UPDATE tasks
        SET planned_details_new =
            jsonb_build_object('type', operation_type, 'note', planned_details)
        WHERE planned_details IS NOT NULL
        """
    )
    for column in ("planned_details", "actual_details"):
        op.execute(
            f"""
            UPDATE operations
            SET {column}_new = jsonb_build_object('type', tasks.operation_type,
                                                  'note', operations.{column})
            FROM tasks
            WHERE tasks.id = operations.task_id AND operations.{column} IS NOT NULL
            """
        )
    _replace_columns()


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.add_column(table, sa.Column(f"{column}_new", sa.Text()))
        op.execute(f"UPDATE {table} SET {column}_new = {column} ->> 'note'")
    _replace_columns()

    # Work of the new types is closest to tillage.
    tasks = sa.table("tasks", sa.column("operation_type", sa.String))
    op.execute(
        tasks.update()
        .where(tasks.c.operation_type.in_(_NEW_TYPES))
        .values(operation_type="tillage")
    )
    op.execute(_operation_types.delete().where(_operation_types.c.code.in_(_NEW_TYPES)))
    for code, position in _OLD_POSITIONS.items():
        _set_position(code, position)


def _set_position(code: str, position: int) -> None:
    op.execute(
        _operation_types.update().where(_operation_types.c.code == code).values(position=position)
    )


def _replace_columns() -> None:
    for table, column in _COLUMNS:
        op.drop_column(table, column)
        op.alter_column(table, f"{column}_new", new_column_name=column)
