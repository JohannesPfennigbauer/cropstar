"""Importing a farmdok field list into a Harvest Year, and undoing imports.

Like the area upload, the preview and the confirmation each read the uploaded report anew;
nothing is kept between requests. Every Field and Plot created belongs to an import batch,
so the whole import can be undone until its areas are used.
"""

import enum
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from geoalchemy2 import WKBElement
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from cropstar_api.farmdok.field_list import FieldList
from cropstar_api.farmdok.field_list_plan import FieldListPlan, GeometryMatch, Reference, plan
from cropstar_api.geometry import to_wgs84_geojson
from cropstar_api.models import (
    AreaSource,
    FarmdokAssignment,
    FarmdokTermKind,
    Field,
    HarvestYearLock,
    ImportBatch,
    ImportKind,
    Operation,
    Plot,
    task_fields,
    task_plots,
)


class Blocker(enum.StrEnum):
    HARVEST_YEAR_LOCKED = "harvest_year_locked"
    # The field list creates a year's areas; it does not reconcile them.
    HARVEST_YEAR_NOT_EMPTY = "harvest_year_not_empty"
    UNKNOWN_CROPS = "unknown_crops"


class UndoRefusal(enum.StrEnum):
    HARVEST_YEAR_LOCKED = "harvest_year_locked"
    # Tasks or Operations refer to the imported areas; undoing would take them along.
    IN_USE = "import_in_use"


@dataclass(frozen=True)
class Borrowed:
    """Geometry from the reference year: as stored, and in WGS84 GeoJSON for display."""

    stored: WKBElement
    wgs84: str


def reference_years(db: Session, farm_id: uuid.UUID) -> set[int]:
    """Harvest Years whose geometry comes from an eAMA export, to borrow from."""
    return set(
        db.scalars(
            select(Field.harvest_year)
            .where(Field.farm_id == farm_id, Field.geometry_source == AreaSource.EAMA_EXPORT)
            .distinct()
        )
    )


def reference(db: Session, farm_id: uuid.UUID, year: int) -> Reference[Borrowed]:
    eama = (Field.farm_id == farm_id, Field.harvest_year == year)
    fields = {
        number: Borrowed(geometry, wgs84)
        for number, geometry, wgs84 in db.execute(
            select(Field.number, Field.geometry, to_wgs84_geojson(Field.geometry)).where(
                *eama, Field.geometry_source == AreaSource.EAMA_EXPORT
            )
        )
    }
    plots: dict[tuple[int, int], Borrowed] = {}
    areas: dict[tuple[int, int], Decimal] = {}
    for field_number, number, area, geometry, wgs84 in db.execute(
        select(
            Field.number,
            Plot.number,
            Plot.declared_area_ha,
            Plot.geometry,
            to_wgs84_geojson(Plot.geometry),
        )
        .join(Field, Plot.field_id == Field.id)
        .where(*eama, Plot.geometry_source == AreaSource.EAMA_EXPORT)
    ):
        plots[(field_number, number)] = Borrowed(geometry, wgs84)
        areas[(field_number, number)] = area
    return Reference(year, fields, plots, areas)


def remembered_crops(db: Session, farm_id: uuid.UUID) -> dict[str, str]:
    """Crop names the Admin assigned in earlier imports, with their AMA Land Use code."""
    rows = db.execute(
        select(FarmdokAssignment.name, FarmdokAssignment.land_use_code).where(
            FarmdokAssignment.farm_id == farm_id,
            FarmdokAssignment.kind == FarmdokTermKind.CROP,
        )
    )
    return {name: code for name, code in rows if code}


def plan_import(
    db: Session,
    farm_id: uuid.UUID,
    field_list: FieldList,
    reference_year: int | None,
    crop_assignments: Mapping[str, str],
) -> FieldListPlan[Borrowed]:
    """Assignments sent now win over remembered ones; remembered ones the list does not use
    are ignored."""
    crop_names = {row.crop for row in field_list.rows}
    remembered = {
        name: code for name, code in remembered_crops(db, farm_id).items() if name in crop_names
    }
    ref = reference(db, farm_id, reference_year) if reference_year is not None else None
    return plan(field_list, ref, remembered | dict(crop_assignments))


def remember(
    db: Session,
    farm_id: uuid.UUID,
    kind: FarmdokTermKind,
    name: str,
    now: datetime,
    *,
    land_use_code: str | None = None,
    operation_type: str | None = None,
    farm_input_id: uuid.UUID | None = None,
) -> None:
    """Keeps an Admin's answer for later imports, replacing an earlier one."""
    found = db.scalar(
        select(FarmdokAssignment).where(
            FarmdokAssignment.farm_id == farm_id,
            FarmdokAssignment.kind == kind,
            FarmdokAssignment.name == name,
        )
    )
    if found is None:
        found = FarmdokAssignment(farm_id=farm_id, kind=kind, name=name)
        db.add(found)
    found.land_use_code = land_use_code
    found.operation_type = operation_type
    found.farm_input_id = farm_input_id
    found.updated_at = now


def blockers(db: Session, farm_id: uuid.UUID, planned: FieldListPlan[Borrowed]) -> list[Blocker]:
    year = planned.harvest_year
    found = []
    if db.get(HarvestYearLock, (farm_id, year)) is not None:
        found.append(Blocker.HARVEST_YEAR_LOCKED)
    has_areas = db.scalar(
        select(exists().where(Field.farm_id == farm_id, Field.harvest_year == year))
    )
    if has_areas:
        found.append(Blocker.HARVEST_YEAR_NOT_EMPTY)
    if planned.unknown_crops:
        found.append(Blocker.UNKNOWN_CROPS)
    return found


def apply(
    db: Session,
    farm_id: uuid.UUID,
    user_id: uuid.UUID,
    source_name: str,
    planned: FieldListPlan[Borrowed],
    now: datetime,
) -> ImportBatch:
    """Creates the year's Fields and Plots; the caller checks `blockers` first."""
    batch = ImportBatch(
        farm_id=farm_id,
        harvest_year=planned.harvest_year,
        kind=ImportKind.FARMDOK_FIELD_LIST,
        source_name=source_name[:300],
        created_by_id=user_id,
        created_at=now,
    )
    db.add(batch)
    db.flush()

    def provenance(geometry: Borrowed | None) -> dict[str, object]:
        if geometry is None:
            return {
                "geometry": None,
                "geometry_source": AreaSource.NONE,
                "borrowed_from_year": None,
            }
        return {
            "geometry": geometry.stored,
            "geometry_source": AreaSource.BORROWED,
            "borrowed_from_year": planned.reference_year,
        }

    fields: dict[int, Field] = {}
    for planned_field in planned.fields:
        field = Field(
            farm_id=farm_id,
            harvest_year=planned.harvest_year,
            number=planned_field.number,
            name=planned_field.name,
            land_use_code=planned_field.land_use_code,
            land_use_name=planned_field.land_use_name,
            declared_area_ha=planned_field.declared_area_ha,
            imported_at=now,
            import_batch_id=batch.id,
            **provenance(planned_field.geometry),
        )
        db.add(field)
        fields[planned_field.number] = field
    db.flush()
    for planned_plot in planned.plots:
        assert planned_plot.land_use is not None
        db.add(
            Plot(
                field_id=fields[planned_plot.field_number].id,
                number=planned_plot.number,
                land_use_code=planned_plot.land_use[0],
                land_use_name=planned_plot.land_use[1],
                declared_area_ha=planned_plot.declared_area_ha,
                imported_at=now,
                import_batch_id=batch.id,
                **provenance(planned_plot.geometry),
            )
        )
    db.flush()
    return batch


def undo_refusal(db: Session, batch: ImportBatch) -> UndoRefusal | None:
    if db.get(HarvestYearLock, (batch.farm_id, batch.harvest_year)) is not None:
        return UndoRefusal.HARVEST_YEAR_LOCKED
    fields = select(Field.id).where(Field.import_batch_id == batch.id)
    plots = select(Plot.id).where(Plot.field_id.in_(fields))
    used = db.scalar(
        select(
            exists().where(task_fields.c.field_id.in_(fields))
            | exists().where(task_plots.c.plot_id.in_(plots))
            | exists().where(Operation.plot_id.in_(plots))
        )
    )
    return UndoRefusal.IN_USE if used else None


def undo(db: Session, batch: ImportBatch) -> None:
    """Removes the batch's Fields (and their Plots); the caller checks `undo_refusal` first."""
    for field in db.scalars(select(Field).where(Field.import_batch_id == batch.id)):
        db.delete(field)
    db.flush()
    db.delete(batch)


def geometry_counts(planned: FieldListPlan[Borrowed]) -> dict[GeometryMatch, int]:
    counts = dict.fromkeys(GeometryMatch, 0)
    for planned_plot in planned.plots:
        counts[planned_plot.match] += 1
    return counts
