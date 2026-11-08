"""Tasks of a Farm. Thin: validation here, rules in the Task lifecycle and Access Policy."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, StringConstraints, field_validator
from sqlalchemy import case, func, nulls_last, or_, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import aliased, selectinload

from cropstar_api.db import Db
from cropstar_api.farms import FarmMembership
from cropstar_api.land_use import LandUseCategory, land_use_category
from cropstar_api.models import (
    FarmInput,
    FarmInputKind,
    Field,
    ImportBatch,
    ImportKind,
    Membership,
    Operation,
    OperationType,
    Plot,
    Priority,
    Task,
    TaskStatus,
    User,
    ValueSource,
    task_plots,
)
from cropstar_api.nutrients import Contents, applied
from cropstar_api.operation_details import FertilisationDetails, OperationDetails, from_stored
from cropstar_api.policy import Action, Actor
from cropstar_api.tasks.lifecycle import (
    AreaNotFoundError,
    DetailsTypeMismatchError,
    DetailsWithoutOperationTypeError,
    FarmInputKindError,
    FarmInputNotFoundError,
    ForbiddenError,
    InvalidAssigneeError,
    InvalidTransitionError,
    MixedHarvestYearsError,
    NewTask,
    OperationDoneError,
    OperationFieldsError,
    OperationNeedsPlotsError,
    OperationNotFoundError,
    StageNotFoundError,
    TaskError,
    TaskLifecycle,
    TaskNotFoundError,
    UnitMismatchError,
    UnknownOperationTypeError,
)
from cropstar_api.tasks.repository import SqlTaskRepository

router = APIRouter(prefix="/farms/{farm_id}", tags=["tasks"])

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]


# ── Schemas ─────────────────────────────────────────────────────────────────


class PersonOut(BaseModel):
    id: uuid.UUID
    email: str


class TaskFieldRef(BaseModel):
    id: uuid.UUID
    number: int
    name: str | None


class TaskPlotRef(BaseModel):
    id: uuid.UUID
    number: int
    field_number: int
    land_use_name: str
    land_use_category: LandUseCategory


class OperationTypeOut(BaseModel):
    code: str


class FarmInputRef(BaseModel):
    id: uuid.UUID
    name: str
    kind: FarmInputKind
    # Archived inputs are no longer offered, but records keep showing them.
    archived: bool


class NutrientsApplied(BaseModel):
    """kg per hectare, from the amount and the input's contents; null where unknown."""

    total_n: float | None
    available_n: float | None
    p2o5: float | None
    k2o: float | None
    # Where the input's contents come from.
    value_source: ValueSource | None
    source_reference: str | None
    analysed_on: date | None


class AppliedInput(BaseModel):
    """The Farm Input Planned or Actual Details refer to, and what it applied."""

    farm_input: FarmInputRef
    # Fertilisation with an amount in a unit that fits the input's contents.
    nutrients: NutrientsApplied | None


class OperationOut(BaseModel):
    id: uuid.UUID
    plot: TaskPlotRef
    status: TaskStatus
    planned_details: OperationDetails | None
    planned_input: AppliedInput | None
    actual_details: OperationDetails | None
    actual_input: AppliedInput | None
    performed_on: date | None
    completed_by: PersonOut | None
    completed_at: datetime | None
    allowed_actions: list[Action]


class OperationLogEntry(BaseModel):
    operation_id: uuid.UUID
    task_id: uuid.UUID
    task_title: str
    operation_type: str
    performed_on: date | None
    actual_details: OperationDetails | None
    actual_input: AppliedInput | None
    completed_by: PersonOut | None
    completed_at: datetime | None


class EarlierOperationLogEntry(OperationLogEntry):
    """A Done Operation of an earlier Harvest Year on the same ground, with where it comes from."""

    harvest_year: int
    field_number: int
    plot_number: int
    # Share of the asking Plot's area the earlier Plot covers, from 0 to 1.
    overlap: float


class ImportedFrom(BaseModel):
    """Where an imported Task came from."""

    kind: ImportKind
    imported_at: datetime


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    due_date: date | None
    priority: Priority
    status: TaskStatus
    assignee: PersonOut | None
    # None with a timestamp means the person has since deleted their account.
    created_by: PersonOut | None
    created_at: datetime
    updated_at: datetime
    completed_by: PersonOut | None
    completed_at: datetime | None
    # Set exactly when the Task refers to Fields or Plots, all of this Harvest Year.
    harvest_year: int | None
    fields: list[TaskFieldRef]
    plots: list[TaskPlotRef]
    # With an Operation Type: one Operation per Plot, and the Status derives from them.
    operation_type: str | None
    planned_details: OperationDetails | None
    planned_input: AppliedInput | None
    operations: list[OperationOut]
    allowed_actions: list[Action]
    # The Farm's Task stage it stands in; meaningful while the Task is Open.
    stage_id: uuid.UUID | None
    # Set for Tasks an import created.
    imported: ImportedFrom | None


class TaskCreate(BaseModel):
    title: Title
    description: Description | None = None
    due_date: date | None = None
    priority: Priority = Priority.NONE
    assignee_id: uuid.UUID | None = None
    done: bool = False
    field_ids: list[uuid.UUID] = []
    plot_ids: list[uuid.UUID] = []
    operation_type: str | None = None
    # Of the Operation Type's kind; copied into each Operation's Planned Details.
    planned_details: OperationDetails | None = None
    # Defaults to the Farm's first stage.
    stage_id: uuid.UUID | None = None

    @field_validator("description")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value or None


class TaskUpdate(BaseModel):
    """Only the fields sent are changed; send null to clear an optional field. Sending
    `field_ids` or `plot_ids` replaces that set of areas."""

    title: Title | None = None
    description: Description | None = None
    due_date: date | None = None
    priority: Priority | None = None
    assignee_id: uuid.UUID | None = None
    field_ids: list[uuid.UUID] | None = None
    plot_ids: list[uuid.UUID] | None = None
    planned_details: OperationDetails | None = None
    stage_id: uuid.UUID | None = None

    @field_validator("title", "priority", "stage_id")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("cannot be cleared")
        return value

    @field_validator("description")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value or None


class OperationUpdate(BaseModel):
    """Only the fields sent are changed; send null to clear one."""

    planned_details: OperationDetails | None = None
    actual_details: OperationDetails | None = None
    performed_on: date | None = None


class OperationCompletion(BaseModel):
    """Optional when completing: without them the plan becomes the record, dated today."""

    actual_details: OperationDetails | None = None
    performed_on: date | None = None


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/operation-types", operation_id="listOperationTypes")
def list_operation_types(membership: FarmMembership, db: Db) -> list[OperationTypeOut]:
    """The kinds of work reports and the model understand; the same for every Farm."""
    codes = db.scalars(select(OperationType.code).order_by(OperationType.position))
    return [OperationTypeOut(code=code) for code in codes]


@router.get("/tasks", operation_id="listTasks")
def list_tasks(
    membership: FarmMembership,
    db: Db,
    status_: Annotated[list[TaskStatus] | None, Query(alias="status")] = None,
    assignee: Annotated[
        str | None, Query(description="A user id, `me` or `none` (unassigned)")
    ] = None,
    priority: Annotated[list[Priority] | None, Query()] = None,
    due_before: Annotated[date | None, Query(description="Due on or before this date")] = None,
    without_due: Annotated[bool, Query(description="Only Tasks without a due date")] = False,
    harvest_year: Annotated[
        int | None,
        Query(description="Tasks of this Harvest Year plus all Tasks without one"),
    ] = None,
    plot_id: Annotated[uuid.UUID | None, Query(description="Only Tasks on this Plot")] = None,
    operation_type: Annotated[list[str] | None, Query()] = None,
) -> list[TaskOut]:
    query = (
        select(Task)
        .where(Task.farm_id == membership.farm_id)
        .options(
            selectinload(Task.fields),
            selectinload(Task.plots).joinedload(Plot.field),
            selectinload(Task.operations).joinedload(Operation.plot).joinedload(Plot.field),
        )
    )
    if operation_type:
        query = query.where(Task.operation_type.in_(operation_type))
    if harvest_year is not None:
        query = query.where(or_(Task.harvest_year == harvest_year, Task.harvest_year.is_(None)))
    if plot_id is not None:
        query = query.where(
            Task.id.in_(select(task_plots.c.task_id).where(task_plots.c.plot_id == plot_id))
        )
    if status_:
        query = query.where(Task.status.in_(status_))
    if assignee == "me":
        query = query.where(Task.assignee_id == membership.user_id)
    elif assignee == "none":
        query = query.where(Task.assignee_id.is_(None))
    elif assignee:
        query = query.where(Task.assignee_id == _uuid(assignee))
    if priority:
        query = query.where(Task.priority.in_(priority))
    if due_before:
        query = query.where(Task.due_date <= due_before)
    if without_due:
        query = query.where(Task.due_date.is_(None))
    status_order = case(
        (Task.status == TaskStatus.OPEN, 0), (Task.status == TaskStatus.DONE, 1), else_=2
    )
    query = query.order_by(
        status_order, nulls_last(Task.due_date.asc()), Task.priority.desc(), Task.created_at.desc()
    )
    tasks = list(db.scalars(query))
    return _out(db, membership, tasks)


@router.post("/tasks", operation_id="createTask", status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, membership: FarmMembership, db: Db) -> TaskOut:
    with _domain_errors():
        fields = body.model_dump(exclude={"field_ids", "plot_ids", "planned_details"})
        new = NewTask(
            **fields,
            field_ids=frozenset(body.field_ids),
            plot_ids=frozenset(body.plot_ids),
            planned_details=body.planned_details,
        )
        task = _lifecycle(db).create(_actor(membership), membership.farm_id, new)
    return _out(db, membership, [task])[0]


@router.get("/tasks/{task_id}", operation_id="getTask")
def read_task(task_id: uuid.UUID, membership: FarmMembership, db: Db) -> TaskOut:
    task = SqlTaskRepository(db).get(membership.farm_id, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=TaskNotFoundError.code)
    return _out(db, membership, [task])[0]


@router.patch("/tasks/{task_id}", operation_id="updateTask")
def update_task(
    task_id: uuid.UUID, body: TaskUpdate, membership: FarmMembership, db: Db
) -> TaskOut:
    changes = {name: getattr(body, name) for name in body.model_fields_set}
    for areas in ("field_ids", "plot_ids"):
        if areas in changes:
            changes[areas] = changes[areas] or []
    with _domain_errors():
        task = _lifecycle(db).edit(_actor(membership), membership.farm_id, task_id, changes)
    return _out(db, membership, [task])[0]


TaskCommand = Literal["complete", "reopen", "discard", "restore"]


@router.post("/tasks/{task_id}/{command}", operation_id="changeTaskStatus")
def change_task_status(
    task_id: uuid.UUID, command: TaskCommand, membership: FarmMembership, db: Db
) -> TaskOut:
    lifecycle = _lifecycle(db)
    with _domain_errors():
        task = getattr(lifecycle, command)(_actor(membership), membership.farm_id, task_id)
    return _out(db, membership, [task])[0]


@router.delete(
    "/tasks/{task_id}",
    operation_id="deleteTask",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_task(task_id: uuid.UUID, membership: FarmMembership, db: Db) -> None:
    """Irreversible. Discarding is the reversible alternative."""
    with _domain_errors():
        _lifecycle(db).delete(_actor(membership), membership.farm_id, task_id)


@router.patch("/tasks/{task_id}/operations/{operation_id}", operation_id="updateOperation")
def update_operation(
    task_id: uuid.UUID,
    operation_id: uuid.UUID,
    body: OperationUpdate,
    membership: FarmMembership,
    db: Db,
) -> TaskOut:
    changes = {name: getattr(body, name) for name in body.model_fields_set}
    with _domain_errors():
        task = _lifecycle(db).edit_operation(
            _actor(membership), membership.farm_id, task_id, operation_id, changes
        )
    return _out(db, membership, [task])[0]


@router.post(
    "/tasks/{task_id}/operations/{operation_id}/{command}",
    operation_id="changeOperationStatus",
)
def change_operation_status(
    task_id: uuid.UUID,
    operation_id: uuid.UUID,
    command: TaskCommand,
    membership: FarmMembership,
    db: Db,
    body: OperationCompletion | None = None,
) -> TaskOut:
    lifecycle = _lifecycle(db)
    actor = _actor(membership)
    with _domain_errors():
        if command == "complete":
            completion = body or OperationCompletion()
            task = lifecycle.complete_operation(
                actor,
                membership.farm_id,
                task_id,
                operation_id,
                completion.actual_details,
                completion.performed_on,
            )
        else:
            task = getattr(lifecycle, f"{command}_operation")(
                actor, membership.farm_id, task_id, operation_id
            )
    return _out(db, membership, [task])[0]


@router.get("/plots/{plot_id}/operations", operation_id="getOperationLog")
def read_operation_log(
    plot_id: uuid.UUID, membership: FarmMembership, db: Db
) -> list[OperationLogEntry]:
    """The Operation Log: every Done Operation on this Plot, oldest first."""
    return [entry for entry, _ in _log_entries(db, membership, [plot_id])]


# An earlier Plot counts as the same ground when it covers at least this share of the Plot.
PREDECESSOR_MIN_OVERLAP = 0.5


@router.get("/plots/{plot_id}/operations/earlier", operation_id="getEarlierOperationLog")
def read_earlier_operation_log(
    plot_id: uuid.UUID, membership: FarmMembership, db: Db
) -> list[EarlierOperationLogEntry]:
    """Done Operations of earlier Harvest Years on the same ground, oldest first.

    Plots belong to one Harvest Year, so the same ground is found by geometry: per earlier
    year, the Plot that covers most of this one, if it covers at least half of it. A Plot
    without geometry has no earlier Operations.
    """
    here = aliased(Plot)
    here_field = aliased(Field)
    overlap = func.ST_Area(func.ST_Intersection(Plot.geometry, here.geometry)) / func.ST_Area(
        here.geometry
    )
    candidates = db.execute(
        select(Plot.id, Plot.number, Field.number, Field.harvest_year, overlap)
        .join(Field, Plot.field_id == Field.id)
        .join(here, func.ST_Intersects(Plot.geometry, here.geometry))
        .join(here_field, here.field_id == here_field.id)
        .where(
            here.id == plot_id,
            here_field.farm_id == membership.farm_id,
            Field.farm_id == membership.farm_id,
            Field.harvest_year < here_field.harvest_year,
        )
    ).all()
    best: dict[int, tuple[uuid.UUID, int, int, float]] = {}
    for earlier_id, plot_number, field_number, year, share in candidates:
        if share >= PREDECESSOR_MIN_OVERLAP and (year not in best or share > best[year][3]):
            best[year] = (earlier_id, field_number, plot_number, float(share))
    origin = {
        plot: (year, field, number, share) for year, (plot, field, number, share) in best.items()
    }
    return [
        EarlierOperationLogEntry(
            **entry.model_dump(),
            harvest_year=origin[plot][0],
            field_number=origin[plot][1],
            plot_number=origin[plot][2],
            overlap=round(origin[plot][3], 3),
        )
        for entry, plot in _log_entries(db, membership, list(origin))
    ]


def _log_entries(
    db: DbSession, membership: Membership, plot_ids: list[uuid.UUID]
) -> list[tuple[OperationLogEntry, uuid.UUID]]:
    """Done Operations on the given Plots, oldest first, each with the Plot it belongs to."""
    if not plot_ids:
        return []
    rows = db.execute(
        select(Operation, Task)
        .join(Task, Operation.task_id == Task.id)
        .where(
            Task.farm_id == membership.farm_id,
            Operation.plot_id.in_(plot_ids),
            Operation.status == TaskStatus.DONE,
        )
        .order_by(nulls_last(Operation.performed_on.asc()), Operation.completed_at.asc())
    ).all()
    people = _people(db, {o.completed_by_id for o, _ in rows if o.completed_by_id})
    inputs = _farm_inputs(db, membership.farm_id, [o.actual_details for o, _ in rows])
    return [
        (
            OperationLogEntry(
                operation_id=operation.id,
                task_id=task.id,
                task_title=task.title,
                operation_type=task.operation_type or "",
                performed_on=operation.performed_on,
                actual_details=from_stored(operation.actual_details),
                actual_input=_applied(operation.actual_details, inputs),
                completed_by=people.get(operation.completed_by_id)
                if operation.completed_by_id
                else None,
                completed_at=operation.completed_at,
            ),
            operation.plot_id,
        )
        for operation, task in rows
    ]


# ── Helpers ─────────────────────────────────────────────────────────────────


def _lifecycle(db: DbSession) -> TaskLifecycle:
    return TaskLifecycle(SqlTaskRepository(db))


def _actor(membership: Membership) -> Actor:
    return Actor(membership.user_id, membership.role)


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_assignee"
        ) from None


@contextmanager
def _domain_errors() -> Iterator[None]:
    try:
        yield
    except TaskNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error.code) from None
    except ForbiddenError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=error.code) from None
    except InvalidTransitionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=error.code) from None
    except OperationNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error.code) from None
    except OperationDoneError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=error.code) from None
    except (
        InvalidAssigneeError,
        AreaNotFoundError,
        MixedHarvestYearsError,
        UnknownOperationTypeError,
        FarmInputNotFoundError,
        FarmInputKindError,
        UnitMismatchError,
        OperationNeedsPlotsError,
        OperationFieldsError,
        DetailsWithoutOperationTypeError,
        DetailsTypeMismatchError,
        StageNotFoundError,
    ) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error.code) from None
    except TaskError as error:  # pragma: no cover - every subclass is mapped above
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=error.code) from None


def _people(db: DbSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, PersonOut]:
    if not ids:
        return {}
    return {
        user.id: PersonOut(id=user.id, email=user.email)
        for user in db.scalars(select(User).where(User.id.in_(ids)))
    }


def _input_id(details: dict[str, Any] | None) -> uuid.UUID | None:
    value = (details or {}).get("farm_input_id")
    return uuid.UUID(value) if isinstance(value, str) else None


def _farm_inputs(
    db: DbSession, farm_id: uuid.UUID, details: list[dict[str, Any] | None]
) -> dict[uuid.UUID, FarmInput]:
    ids = {i for i in map(_input_id, details) if i is not None}
    if not ids:
        return {}
    query = select(FarmInput).where(FarmInput.farm_id == farm_id, FarmInput.id.in_(ids))
    return {item.id: item for item in db.scalars(query)}


def _applied(
    details: dict[str, Any] | None, inputs: dict[uuid.UUID, FarmInput]
) -> AppliedInput | None:
    item = inputs.get(_input_id(details) or uuid.UUID(int=0))
    if item is None:
        return None
    parsed = from_stored(details)
    nutrients = None
    if (
        isinstance(parsed, FertilisationDetails)
        and parsed.amount is not None
        and parsed.unit is not None
        and item.unit is not None
    ):
        result = applied(
            Decimal(str(parsed.amount)),
            parsed.unit,
            Contents(item.unit, item.total_n, item.available_n, item.p2o5, item.k2o),
        )
        if result is not None:
            nutrients = NutrientsApplied(
                total_n=_float(result.total_n),
                available_n=_float(result.available_n),
                p2o5=_float(result.p2o5),
                k2o=_float(result.k2o),
                value_source=item.value_source,
                source_reference=item.source_reference,
                analysed_on=item.analysed_on,
            )
    return AppliedInput(
        farm_input=FarmInputRef(
            id=item.id, name=item.name, kind=item.kind, archived=item.archived_at is not None
        ),
        nutrients=nutrients,
    )


def _float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _plot_ref(plot: Plot) -> TaskPlotRef:
    return TaskPlotRef(
        id=plot.id,
        number=plot.number,
        field_number=plot.field.number,
        land_use_name=plot.land_use_name,
        land_use_category=land_use_category(plot.land_use_code),
    )


def _out(db: DbSession, membership: Membership, tasks: list[Task]) -> list[TaskOut]:
    people = _people(
        db,
        {
            person_id
            for task in tasks
            for person_id in (
                task.assignee_id,
                task.created_by_id,
                task.completed_by_id,
                *(o.completed_by_id for o in task.operations),
            )
            if person_id is not None
        },
    )

    def person(person_id: uuid.UUID | None) -> PersonOut | None:
        return people.get(person_id) if person_id else None

    inputs = _farm_inputs(
        db,
        membership.farm_id,
        [
            details
            for task in tasks
            for details in (
                task.planned_details,
                *(o.planned_details for o in task.operations),
                *(o.actual_details for o in task.operations),
            )
        ],
    )
    batch_ids = {task.import_batch_id for task in tasks if task.import_batch_id}
    batches = (
        {b.id: b for b in db.scalars(select(ImportBatch).where(ImportBatch.id.in_(batch_ids)))}
        if batch_ids
        else {}
    )

    def imported(task: Task) -> ImportedFrom | None:
        batch = batches.get(task.import_batch_id) if task.import_batch_id else None
        return ImportedFrom(kind=batch.kind, imported_at=batch.created_at) if batch else None

    lifecycle = _lifecycle(db)
    actor = _actor(membership)
    return [
        TaskOut(
            id=task.id,
            title=task.title,
            description=task.description,
            due_date=task.due_date,
            priority=task.priority,
            status=task.status,
            assignee=person(task.assignee_id),
            created_by=person(task.created_by_id),
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_by=person(task.completed_by_id),
            completed_at=task.completed_at,
            harvest_year=task.harvest_year,
            fields=[TaskFieldRef(id=f.id, number=f.number, name=f.name) for f in task.fields],
            plots=[_plot_ref(p) for p in task.plots],
            operation_type=task.operation_type,
            planned_details=from_stored(task.planned_details),
            planned_input=_applied(task.planned_details, inputs),
            operations=[
                OperationOut(
                    id=o.id,
                    plot=_plot_ref(o.plot),
                    status=o.status,
                    planned_details=from_stored(o.planned_details),
                    planned_input=_applied(o.planned_details, inputs),
                    actual_details=from_stored(o.actual_details),
                    actual_input=_applied(o.actual_details, inputs),
                    performed_on=o.performed_on,
                    completed_by=person(o.completed_by_id),
                    completed_at=o.completed_at,
                    allowed_actions=lifecycle.operation_allowed_actions(actor, task, o),
                )
                for o in sorted(task.operations, key=lambda o: (o.plot.field.number, o.plot.number))
            ],
            allowed_actions=lifecycle.allowed_actions(actor, task),
            stage_id=task.stage_id,
            imported=imported(task),
        )
        for task in tasks
    ]
