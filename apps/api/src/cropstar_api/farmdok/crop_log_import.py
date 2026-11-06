"""Importing a farmdok crop production log into a Harvest Year, and undoing it.

Like the field list, the preview and the confirmation each read the report anew. Every
Task created belongs to an import batch; Farm Inputs created on the way are kept on undo,
as they belong to the Farm, not to the import.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from cropstar_api.farmdok.crop_log import CropLog
from cropstar_api.farmdok.crop_log_plan import (
    CropLogPlan,
    KnownInput,
    Resolutions,
    YearPlot,
    plan,
)
from cropstar_api.farmdok.field_list_import import remember, remembered_crops
from cropstar_api.land_use import land_use_names
from cropstar_api.models import (
    FarmdokAssignment,
    FarmdokTermKind,
    FarmInput,
    Field,
    HarvestYearLock,
    ImportBatch,
    ImportKind,
    Operation,
    OperationType,
    Plot,
    Priority,
    Task,
    TaskStatus,
)
from cropstar_api.operation_details import FertilisationDetails, SowingDetails, to_stored


class Blocker(enum.StrEnum):
    HARVEST_YEAR_LOCKED = "harvest_year_locked"
    ALREADY_IMPORTED = "already_imported"
    UNRESOLVED = "unresolved"


class UndoRefusal(enum.StrEnum):
    HARVEST_YEAR_LOCKED = "harvest_year_locked"
    # Imported Tasks were changed since: undoing would throw that work away.
    EDITED = "import_edited"


def year_plots(db: Session, farm_id: uuid.UUID, year: int) -> list[YearPlot]:
    rows = db.execute(
        select(Plot.id, Field.number, Plot.number, Plot.land_use_code)
        .join(Field, Plot.field_id == Field.id)
        .where(Field.farm_id == farm_id, Field.harvest_year == year)
    )
    return [YearPlot(*row) for row in rows]


def known_inputs(db: Session, farm_id: uuid.UUID) -> list[KnownInput]:
    return [
        KnownInput(i.id, i.name, i.kind, i.unit, i.archived_at is not None)
        for i in db.scalars(select(FarmInput).where(FarmInput.farm_id == farm_id))
    ]


def plan_import(
    db: Session, farm_id: uuid.UUID, log: CropLog, resolutions: Resolutions
) -> CropLogPlan:
    remembered = list(
        db.scalars(select(FarmdokAssignment).where(FarmdokAssignment.farm_id == farm_id))
    )
    return plan(
        log,
        year_plots(db, farm_id, log.harvest_year),
        known_inputs(db, farm_id),
        set(db.scalars(select(OperationType.code))),
        {a.name: a.operation_type for a in remembered if a.kind is FarmdokTermKind.ACTIVITY},
        {a.name: a.farm_input_id for a in remembered if a.kind is FarmdokTermKind.PRODUCT},
        resolutions,
        remembered_crops(db, farm_id),
    )


def blockers(db: Session, farm_id: uuid.UUID, planned: CropLogPlan) -> list[Blocker]:
    year = planned.harvest_year
    found = []
    if db.get(HarvestYearLock, (farm_id, year)) is not None:
        found.append(Blocker.HARVEST_YEAR_LOCKED)
    imported = db.scalar(
        select(
            exists().where(
                ImportBatch.farm_id == farm_id,
                ImportBatch.harvest_year == year,
                ImportBatch.kind == ImportKind.FARMDOK_CROP_LOG,
            )
        )
    )
    if imported:
        found.append(Blocker.ALREADY_IMPORTED)
    if planned.unresolved:
        found.append(Blocker.UNRESOLVED)
    return found


def apply(
    db: Session,
    farm_id: uuid.UUID,
    user_id: uuid.UUID,
    source_name: str,
    planned: CropLogPlan,
    resolutions: Resolutions,
    now: datetime,
) -> ImportBatch:
    """Creates the Done Tasks and any new Farm Inputs, and remembers the Admin's answers;
    the caller checks `blockers` first."""
    batch = ImportBatch(
        farm_id=farm_id,
        harvest_year=planned.harvest_year,
        kind=ImportKind.FARMDOK_CROP_LOG,
        source_name=source_name[:300],
        created_by_id=user_id,
        created_at=now,
    )
    db.add(batch)

    created: dict[str, uuid.UUID] = {}
    names = land_use_names()
    for new in planned.new_inputs:
        item = FarmInput(
            id=uuid.uuid4(),
            farm_id=farm_id,
            kind=new.kind,
            name=new.name[:200],
            unit=new.unit,
            land_use_code=new.land_use_code,
            land_use_name=names.get(new.land_use_code) if new.land_use_code else None,
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        created[new.name] = item.id
    db.flush()

    plots = {p.id: p for p in db.scalars(select(Plot).where(Plot.id.in_(_all_plots(planned))))}
    for planned_task in planned.tasks:
        details = planned_task.details
        if planned_task.new_input is not None and isinstance(
            details, SowingDetails | FertilisationDetails
        ):
            details = details.model_copy(update={"farm_input_id": created[planned_task.new_input]})
        stored = to_stored(details)
        task = Task(
            id=uuid.uuid4(),
            farm_id=farm_id,
            title=planned_task.title[:200],
            priority=Priority.NONE,
            status=TaskStatus.DONE,
            created_by_id=user_id,
            created_at=now,
            updated_at=now,
            completed_by_id=user_id,
            completed_at=now,
            harvest_year=planned.harvest_year,
            operation_type=planned_task.operation_type,
            planned_details=stored,
            import_batch_id=batch.id,
        )
        task.plots = [plots[i] for i in planned_task.plot_ids]
        task.operations = [
            Operation(
                id=uuid.uuid4(),
                task_id=task.id,
                plot_id=plot_id,
                status=TaskStatus.DONE,
                planned_details=stored,
                actual_details=stored,
                performed_on=planned_task.performed_on,
                completed_by_id=user_id,
                completed_at=now,
            )
            for plot_id in planned_task.plot_ids
        ]
        db.add(task)

    for name, operation_type in resolutions.activities.items():
        remember(db, farm_id, FarmdokTermKind.ACTIVITY, name, now, operation_type=operation_type)
    for name, choice in resolutions.products.items():
        input_id = created.get(name) if choice.create else choice.farm_input_id
        remember(db, farm_id, FarmdokTermKind.PRODUCT, name, now, farm_input_id=input_id)
    db.flush()
    return batch


def undo_refusal(db: Session, batch: ImportBatch) -> UndoRefusal | None:
    if db.get(HarvestYearLock, (batch.farm_id, batch.harvest_year)) is not None:
        return UndoRefusal.HARVEST_YEAR_LOCKED
    # Every change to a Task or its Operations moves its `updated_at`.
    edited = db.scalar(
        select(
            exists().where(Task.import_batch_id == batch.id, Task.updated_at != batch.created_at)
        )
    )
    return UndoRefusal.EDITED if edited else None


def undo(db: Session, batch: ImportBatch) -> None:
    for task in db.scalars(select(Task).where(Task.import_batch_id == batch.id)):
        db.delete(task)
    db.flush()
    db.delete(batch)


def _all_plots(planned: CropLogPlan) -> set[uuid.UUID]:
    return {plot_id for task in planned.tasks for plot_id in task.plot_ids}
