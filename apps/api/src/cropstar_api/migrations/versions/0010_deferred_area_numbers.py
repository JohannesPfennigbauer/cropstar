"""Field and Plot numbers need to be unique only once a transaction ends

An area upload may swap or shift numbers within a Harvest Year; checked row by row, the
intermediate states would collide.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINTS = (
    ("uq_fields_farm_id", "fields", ["farm_id", "harvest_year", "number"]),
    ("uq_plots_field_id", "plots", ["field_id", "number"]),
)


def upgrade() -> None:
    for name, table, columns in _CONSTRAINTS:
        op.drop_constraint(name, table, type_="unique")
        op.create_unique_constraint(name, table, columns, deferrable=True, initially="DEFERRED")


def downgrade() -> None:
    for name, table, columns in _CONSTRAINTS:
        op.drop_constraint(name, table, type_="unique")
        op.create_unique_constraint(name, table, columns)
