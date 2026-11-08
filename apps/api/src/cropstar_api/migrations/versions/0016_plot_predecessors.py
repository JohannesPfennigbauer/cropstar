"""Plot predecessors: Plots of the nearest earlier Harvest Year on the same ground

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# As in `plot_lineage`, copied so this migration never changes: a Plot of the nearest earlier
# Harvest Year is a Predecessor when the shared area is at least half of the smaller Plot.
_BACKFILL = """
    INSERT INTO plot_predecessors (plot_id, predecessor_id, overlap)
    SELECT p.id, q.id,
           ST_Area(ST_Intersection(p.geometry, q.geometry)) / ST_Area(p.geometry)
    FROM plots p
    JOIN fields f ON f.id = p.field_id
    JOIN fields g ON g.farm_id = f.farm_id AND g.harvest_year = (
        SELECT max(h.harvest_year) FROM fields h
        WHERE h.farm_id = f.farm_id AND h.harvest_year < f.harvest_year
    )
    JOIN plots q ON q.field_id = g.id AND ST_Intersects(p.geometry, q.geometry)
    WHERE ST_Area(ST_Intersection(p.geometry, q.geometry))
          >= 0.5 * LEAST(ST_Area(p.geometry), ST_Area(q.geometry))
"""


def upgrade() -> None:
    op.create_table(
        "plot_predecessors",
        sa.Column("plot_id", sa.Uuid(), nullable=False),
        sa.Column("predecessor_id", sa.Uuid(), nullable=False),
        sa.Column("overlap", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.ForeignKeyConstraint(
            ["plot_id"],
            ["plots.id"],
            name=op.f("fk_plot_predecessors_plot_id_plots"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_id"],
            ["plots.id"],
            name=op.f("fk_plot_predecessors_predecessor_id_plots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("plot_id", "predecessor_id", name=op.f("pk_plot_predecessors")),
    )
    op.create_index(
        op.f("ix_plot_predecessors_predecessor_id"), "plot_predecessors", ["predecessor_id"]
    )
    op.execute(_BACKFILL)


def downgrade() -> None:
    op.drop_index(op.f("ix_plot_predecessors_predecessor_id"), table_name="plot_predecessors")
    op.drop_table("plot_predecessors")
