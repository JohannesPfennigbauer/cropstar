"""Plot lineage: which Plots of the year before lie on the same ground.

Plots belong to one Harvest Year, so the same ground is found by geometry. A Plot of the
nearest earlier Harvest Year is a Predecessor when the shared area is at least half of the
smaller of the two: that covers a split (the old Plot is large) as well as a merger (several
old Plots, each mostly inside the new one). Links are stored with the share of the Plot the
Predecessor covers, and renewed whenever a Harvest Year's areas change.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

# Share of the smaller Plot the shared area must reach.
MIN_SHARED = 0.5

# The nearest earlier Harvest Year of the same Farm that has Fields.
_LINK = text(
    """
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
    WHERE f.farm_id = :farm_id AND f.harvest_year = :harvest_year
      AND ST_Area(ST_Intersection(p.geometry, q.geometry))
          >= :min_shared * LEAST(ST_Area(p.geometry), ST_Area(q.geometry))
    """
)

_UNLINK = text(
    """
    DELETE FROM plot_predecessors
    WHERE plot_id IN (
        SELECT p.id FROM plots p JOIN fields f ON f.id = p.field_id
        WHERE f.farm_id = :farm_id AND f.harvest_year = :harvest_year
    )
    """
)

_NEXT_YEAR = text(
    "SELECT min(harvest_year) FROM fields WHERE farm_id = :farm_id AND harvest_year > :harvest_year"
)


def relink(db: Session, farm_id: uuid.UUID, harvest_year: int) -> None:
    """Renews the Predecessors of a Harvest Year's Plots and of the next later year's Plots,
    whose nearest earlier year may just have changed."""
    db.flush()
    later = db.execute(_NEXT_YEAR, {"farm_id": farm_id, "harvest_year": harvest_year}).scalar()
    for year in (harvest_year, later):
        if year is None:
            continue
        params = {"farm_id": farm_id, "harvest_year": year}
        db.execute(_UNLINK, params)
        db.execute(_LINK, params | {"min_shared": MIN_SHARED})


# A Plot's Predecessors and theirs, back through all earlier Harvest Years. Mergers make it a
# graph rather than a chain; each earlier Plot appears once.
_LINEAGE = text(
    """
    WITH RECURSIVE lineage(plot_id, depth) AS (
        SELECT pp.predecessor_id, 1
        FROM plot_predecessors pp
        JOIN plots p ON p.id = pp.plot_id
        JOIN fields f ON f.id = p.field_id
        WHERE pp.plot_id = :plot_id AND f.farm_id = :farm_id
        UNION
        SELECT pp.predecessor_id, l.depth + 1
        FROM plot_predecessors pp JOIN lineage l ON pp.plot_id = l.plot_id
        WHERE l.depth < 100
    )
    SELECT DISTINCT q.id, g.harvest_year, g.number AS field_number, q.number AS plot_number,
           q.land_use_code, q.land_use_name,
           COALESCE(
               ST_Area(ST_Intersection(q.geometry, here.geometry))
               / NULLIF(ST_Area(here.geometry), 0),
               0
           ) AS overlap
    FROM lineage l
    JOIN plots q ON q.id = l.plot_id
    JOIN fields g ON g.id = q.field_id
    JOIN plots here ON here.id = :plot_id
    ORDER BY g.harvest_year DESC, overlap DESC, plot_number
    """
)


@dataclass(frozen=True)
class EarlierPlot:
    id: uuid.UUID
    harvest_year: int
    field_number: int
    plot_number: int
    land_use_code: str
    land_use_name: str
    # Share of the asking Plot's area this earlier Plot covers, from 0 to 1.
    overlap: float


def lineage(db: Session, farm_id: uuid.UUID, plot_id: uuid.UUID) -> list[EarlierPlot]:
    """All earlier Plots on the same ground, newest Harvest Year first."""
    rows = db.execute(_LINEAGE, {"plot_id": plot_id, "farm_id": farm_id}).all()
    return [
        EarlierPlot(
            id=row.id,
            harvest_year=row.harvest_year,
            field_number=row.field_number,
            plot_number=row.plot_number,
            land_use_code=row.land_use_code,
            land_use_name=row.land_use_name,
            overlap=round(float(row.overlap), 3),
        )
        for row in rows
    ]
