"""Area upload: a Harvest Year's Fields and Plots from the Farm's eAMA export.

Stateless: the preview and the confirmation each read the uploaded export anew and
reconcile it with the year's current areas using the Admin's assignments, so neither files
nor half-finished uploads are kept on the server.
"""

import uuid
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from cropstar_api import area_reconciliation
from cropstar_api.area_reconciliation import ExistingArea, Plan
from cropstar_api.eama import AreaDeclaration
from cropstar_api.geometry import from_ama_geojson
from cropstar_api.models import (
    AreaSource,
    Field,
    HarvestYearLock,
    Operation,
    Plot,
    Task,
    task_fields,
    task_plots,
)


@dataclass(frozen=True)
class TaskRef:
    id: uuid.UUID
    title: str


@dataclass(frozen=True)
class CurrentAreas:
    """A Harvest Year's areas as they are now, and the Tasks that refer to them."""

    fields: list[Field]
    plots: list[Plot]
    # By Field or Plot id; only areas some Task refers to.
    tasks: dict[uuid.UUID, list[TaskRef]]
    locked: bool


def current_areas(db: Session, farm_id: uuid.UUID, harvest_year: int) -> CurrentAreas:
    fields = list(
        db.scalars(
            select(Field)
            .where(Field.farm_id == farm_id, Field.harvest_year == harvest_year)
            .options(selectinload(Field.plots))
            .order_by(Field.number)
        )
    )
    plots = [plot for field in fields for plot in sorted(field.plots, key=lambda p: p.number)]
    field_ids = [f.id for f in fields]
    plot_ids = [p.id for p in plots]
    references = [
        select(task_fields.c.field_id, Task.id, Task.title)
        .join(Task, Task.id == task_fields.c.task_id)
        .where(task_fields.c.field_id.in_(field_ids)),
        select(task_plots.c.plot_id, Task.id, Task.title)
        .join(Task, Task.id == task_plots.c.task_id)
        .where(task_plots.c.plot_id.in_(plot_ids)),
        select(Operation.plot_id, Task.id, Task.title)
        .join(Task, Task.id == Operation.task_id)
        .where(Operation.plot_id.in_(plot_ids)),
    ]
    tasks: dict[uuid.UUID, set[TaskRef]] = defaultdict(set)
    for query in references:
        for area_id, task_id, title in db.execute(query):
            tasks[area_id].add(TaskRef(task_id, title))
    locked = db.get(HarvestYearLock, (farm_id, harvest_year)) is not None
    return CurrentAreas(
        fields,
        plots,
        {area: sorted(refs, key=lambda r: (r.title, r.id)) for area, refs in tasks.items()},
        locked,
    )


def reconcile(
    current: CurrentAreas,
    declaration: AreaDeclaration,
    assignments: Mapping[str, uuid.UUID | None],
) -> Plan:
    """Raises `InvalidAssignmentError` for assignments that do not fit the export."""
    return area_reconciliation.reconcile(
        [
            ExistingArea(
                id=field.id,
                number=field.number,
                name=field.name,
                land_use_code=field.land_use_code,
                land_use_name=field.land_use_name,
                declared_area_ha=field.declared_area_ha,
                geometry=to_shape(field.geometry),
                from_eama=field.geometry_source == AreaSource.EAMA_EXPORT,
                referenced=field.id in current.tasks,
            )
            for field in current.fields
        ],
        [
            ExistingArea(
                id=plot.id,
                field_id=plot.field_id,
                number=plot.number,
                land_use_code=plot.land_use_code,
                land_use_name=plot.land_use_name,
                declared_area_ha=plot.declared_area_ha,
                geometry=to_shape(plot.geometry),
                from_eama=plot.geometry_source == AreaSource.EAMA_EXPORT,
                referenced=plot.id in current.tasks,
            )
            for plot in current.plots
        ],
        declaration,
        assignments,
        locked=current.locked,
    )


def apply(
    db: Session,
    farm_id: uuid.UUID,
    declaration: AreaDeclaration,
    current: CurrentAreas,
    plan: Plan,
    imported_at: datetime,
) -> None:
    """Make the year match the declaration; the caller checks the plan's blockers first.

    Assigned areas are updated in place, so their Tasks and Operations stay attached."""
    fields_by_id = {field.id: field for field in current.fields}
    plots_by_id = {plot.id: plot for plot in current.plots}

    fields: dict[int, Field] = {}
    for declared, entry in zip(declaration.fields, plan.fields, strict=True):
        if entry.target is None:
            field = Field(farm_id=farm_id, harvest_year=declaration.harvest_year)
            db.add(field)
        else:
            field = fields_by_id[entry.target]
        field.number = declared.number
        field.name = declared.name
        field.land_use_code = declared.land_use_code
        field.land_use_name = declared.land_use_name
        field.declared_area_ha = declared.declared_area_ha
        field.geometry = from_ama_geojson(declared.geometry)
        field.geometry_source = AreaSource.EAMA_EXPORT
        field.imported_at = imported_at
        fields[declared.number] = field

    for declared_plot, entry in zip(declaration.plots, plan.plots, strict=True):
        plot = Plot() if entry.target is None else plots_by_id[entry.target]
        plot.field = fields[declared_plot.field_number]
        plot.number = declared_plot.number
        plot.land_use_code = declared_plot.land_use_code
        plot.land_use_name = declared_plot.land_use_name
        plot.declared_area_ha = declared_plot.declared_area_ha
        plot.geometry = from_ama_geojson(declared_plot.geometry)
        plot.geometry_source = AreaSource.EAMA_EXPORT
        plot.imported_at = imported_at
        db.add(plot)
    # Moved Plots must have left their old Field before a removed Field takes its Plots along.
    db.flush()
    removed_fields = set(plan.removed_fields)
    for plot_id in plan.removed_plots:
        if plots_by_id[plot_id].field_id not in removed_fields:
            db.delete(plots_by_id[plot_id])
    for field_id in plan.removed_fields:
        db.delete(fields_by_id[field_id])
    db.flush()
