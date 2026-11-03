"""Area provenance: where the geometry of Fields and Plots came from, and when

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

area_source = postgresql.ENUM("eama_export", "invekos_open_data", name="area_source")


def upgrade() -> None:
    area_source.create(op.get_bind())
    for table in ("fields", "plots"):
        # Until now only the demo seed created areas, from public INVEKOS data.
        op.add_column(
            table,
            sa.Column(
                "geometry_source",
                postgresql.ENUM(name="area_source", create_type=False),
                nullable=False,
                server_default="invekos_open_data",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "imported_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.alter_column(table, "geometry_source", server_default=None)
        op.alter_column(table, "imported_at", server_default=None)


def downgrade() -> None:
    for table in ("fields", "plots"):
        op.drop_column(table, "imported_at")
        op.drop_column(table, "geometry_source")
    area_source.drop(op.get_bind())
