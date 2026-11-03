"""Area upload: a Harvest Year's Fields and Plots from the Farm's eAMA export.

Stateless: the preview and the confirmation each read the uploaded export anew, so neither
files nor half-finished uploads are kept on the server.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from cropstar_api.eama import AreaDeclaration
from cropstar_api.geometry import from_ama_geojson
from cropstar_api.models import AreaSource, Field, HarvestYearLock, Plot


class Blocker(enum.StrEnum):
    HARVEST_YEAR_LOCKED = "harvest_year_locked"
    # Reconciling with existing areas comes later; until then only empty years.
    HARVEST_YEAR_NOT_EMPTY = "harvest_year_not_empty"


def blockers(db: Session, farm_id: uuid.UUID, harvest_year: int) -> list[Blocker]:
    found = []
    if db.get(HarvestYearLock, (farm_id, harvest_year)) is not None:
        found.append(Blocker.HARVEST_YEAR_LOCKED)
    has_fields = db.scalar(
        select(Field.id)
        .where(Field.farm_id == farm_id, Field.harvest_year == harvest_year)
        .limit(1)
    )
    if has_fields is not None:
        found.append(Blocker.HARVEST_YEAR_NOT_EMPTY)
    return found


def apply(
    db: Session, farm_id: uuid.UUID, declaration: AreaDeclaration, imported_at: datetime
) -> None:
    """Create the declared Fields and Plots; the caller checks `blockers` first."""
    fields: dict[int, Field] = {}
    for declared in declaration.fields:
        field = Field(
            farm_id=farm_id,
            harvest_year=declaration.harvest_year,
            number=declared.number,
            name=declared.name,
            land_use_code=declared.land_use_code,
            land_use_name=declared.land_use_name,
            declared_area_ha=declared.declared_area_ha,
            geometry=from_ama_geojson(declared.geometry),
            geometry_source=AreaSource.EAMA_EXPORT,
            imported_at=imported_at,
        )
        db.add(field)
        fields[declared.number] = field
    db.flush()
    db.add_all(
        Plot(
            field_id=fields[declared.field_number].id,
            number=declared.number,
            land_use_code=declared.land_use_code,
            land_use_name=declared.land_use_name,
            declared_area_ha=declared.declared_area_ha,
            geometry=from_ama_geojson(declared.geometry),
            geometry_source=AreaSource.EAMA_EXPORT,
            imported_at=imported_at,
        )
        for declared in declaration.plots
    )
    db.flush()
