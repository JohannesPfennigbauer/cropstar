"""Farm Inputs: the fertilisers, seed and other inputs of a Farm

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENUMS = {
    "farm_input_kind": ("fertiliser", "seed", "other"),
    "farm_input_unit": ("t", "m3", "100kg"),
    "value_source": ("standard_value", "lab_analysis", "manufacturer"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    for name, values in _ENUMS.items():
        postgresql.ENUM(*values, name=name).create(op.get_bind())
    op.create_table(
        "farm_inputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("kind", _enum("farm_input_kind"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("unit", _enum("farm_input_unit"), nullable=True),
        sa.Column("dry_matter_percent", sa.Numeric(6, 2), nullable=True),
        sa.Column("total_n", sa.Numeric(8, 3), nullable=True),
        sa.Column("available_n", sa.Numeric(8, 3), nullable=True),
        sa.Column("p2o5", sa.Numeric(8, 3), nullable=True),
        sa.Column("k2o", sa.Numeric(8, 3), nullable=True),
        sa.Column("value_source", _enum("value_source"), nullable=True),
        sa.Column("source_reference", sa.String(length=500), nullable=True),
        sa.Column("analysed_on", sa.Date(), nullable=True),
        sa.Column("catalogue_entry", sa.String(length=50), nullable=True),
        sa.Column("land_use_code", sa.String(length=10), nullable=True),
        sa.Column("land_use_name", sa.String(length=200), nullable=True),
        sa.Column("variety", sa.String(length=200), nullable=True),
        sa.Column("thousand_kernel_weight_g", sa.Numeric(8, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farms.id"], name=op.f("fk_farm_inputs_farm_id_farms"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_farm_inputs")),
    )
    op.create_index("ix_farm_inputs_farm_id_kind", "farm_inputs", ["farm_id", "kind"])


def downgrade() -> None:
    op.drop_table("farm_inputs")
    for name in _ENUMS:
        postgresql.ENUM(name=name).drop(op.get_bind())
