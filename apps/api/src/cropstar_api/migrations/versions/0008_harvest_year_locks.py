"""Harvest Year locks

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "harvest_year_locks",
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("harvest_year", sa.SmallInteger(), nullable=False),
        sa.Column("locked_by_id", sa.Uuid(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farms.id"],
            name=op.f("fk_harvest_year_locks_farm_id_farms"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["locked_by_id"],
            ["users.id"],
            name=op.f("fk_harvest_year_locks_locked_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("farm_id", "harvest_year", name=op.f("pk_harvest_year_locks")),
    )


def downgrade() -> None:
    op.drop_table("harvest_year_locks")
