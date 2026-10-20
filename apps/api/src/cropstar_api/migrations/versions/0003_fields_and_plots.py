"""Fields and plots per harvest year

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fields",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("harvest_year", sa.SmallInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("land_use_code", sa.String(length=10), nullable=False),
        sa.Column("land_use_name", sa.String(length=200), nullable=False),
        sa.Column("declared_area_ha", sa.Numeric(10, 4), nullable=False),
        sa.Column(
            "geometry",
            Geometry("MULTIPOLYGON", srid=31287, spatial_index=False),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farms.id"], name=op.f("fk_fields_farm_id_farms"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fields")),
        sa.UniqueConstraint("farm_id", "harvest_year", "number", name=op.f("uq_fields_farm_id")),
    )
    op.create_index("ix_fields_farm_id_harvest_year", "fields", ["farm_id", "harvest_year"])
    op.create_index("idx_fields_geometry", "fields", ["geometry"], postgresql_using="gist")

    op.create_table(
        "plots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("field_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("land_use_code", sa.String(length=10), nullable=False),
        sa.Column("land_use_name", sa.String(length=200), nullable=False),
        sa.Column("declared_area_ha", sa.Numeric(10, 4), nullable=False),
        sa.Column(
            "geometry",
            Geometry("MULTIPOLYGON", srid=31287, spatial_index=False),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["field_id"], ["fields.id"], name=op.f("fk_plots_field_id_fields"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plots")),
        sa.UniqueConstraint("field_id", "number", name=op.f("uq_plots_field_id")),
    )
    op.create_index(op.f("ix_plots_field_id"), "plots", ["field_id"])
    op.create_index("idx_plots_geometry", "plots", ["geometry"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_table("plots")
    op.drop_table("fields")
