"""Tasks of a Farm. Thin: validation here, rules in the Task lifecycle and Access Policy."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, StringConstraints, field_validator
from sqlalchemy import case, nulls_last, or_, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from cropstar_api.db import Db
from cropstar_api.farms import FarmMembership
from cropstar_api.land_use import LandUseCategory, land_use_category
from cropstar_api.models import (
    Membership,
    Operation,
    OperationType,
    Plot,
    Priority,
    Task,
    TaskStatus,
    User,
    task_plots,
)
from cropstar_api.policy import Action, Actor
from cropstar_api.tasks.lifecycle import (
    AreaNotFoundError,
    ForbiddenError,
    InvalidAssigneeError,
    InvalidTransitionError,
    MixedHarvestYearsError,
    NewTask,
    OperationDoneError,
    OperationFieldsError,
    OperationNeedsPlotsError,
    OperationNotFoundError,
    TaskError,
    TaskLifecycle,
    TaskNotFoundError,
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


class OperationOut(BaseModel):
    id: uuid.UUID
    plot: TaskPlotRef
    status: TaskStatus
    planned_details: str | None
    actual_details: str | None
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
    actual_details: str | None
    completed_by: PersonOut | None
    completed_at: datetime | None


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
    planned_details: str | None
    operations: list[OperationOut]
    allowed_actions: list[Action]


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
    planned_details: Description | None = None

    @field_validator("description", "planned_details")
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
    planned_details: Description | None = None

    @field_validator("title", "priority")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("cannot be cleared")
        return value

    @field_validator("description", "planned_details")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value or None


class OperationUpdate(BaseModel):
    """Only the fields sent are changed; send null to clear one."""

    planned_details: Description | None = None
    actual_details: Description | None = None
    performed_on: date | None = None


class OperationCompletion(BaseModel):
    """Optional when completing: without them the plan becomes the record, dated today."""

    actual_details: Description | None = None
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
        fields = body.model_dump(exclude={"field_ids", "plot_ids"})
        new = NewTask(
            **fields, field_ids=frozenset(body.field_ids), plot_ids=frozenset(body.plot_ids)
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
    rows = db.execute(
        select(Operation, Task)
        .join(Task, Operation.task_id == Task.id)
        .where(
            Task.farm_id == membership.farm_id,
            Operation.plot_id == plot_id,
            Operation.status == TaskStatus.DONE,
        )
        .order_by(nulls_last(Operation.performed_on.asc()), Operation.completed_at.asc())
    ).all()
    people = _people(db, {o.completed_by_id for o, _ in rows if o.completed_by_id})
    return [
        OperationLogEntry(
            operation_id=operation.id,
            task_id=task.id,
            task_title=task.title,
            operation_type=task.operation_type or "",
            performed_on=operation.performed_on,
            actual_details=operation.actual_details,
            completed_by=people.get(operation.completed_by_id)
            if operation.completed_by_id
            else None,
            completed_at=operation.completed_at,
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
        OperationNeedsPlotsError,
        OperationFieldsError,
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
            planned_details=task.planned_details,
            operations=[
                OperationOut(
                    id=o.id,
                    plot=_plot_ref(o.plot),
                    status=o.status,
                    planned_details=o.planned_details,
                    actual_details=o.actual_details,
                    performed_on=o.performed_on,
                    completed_by=person(o.completed_by_id),
                    completed_at=o.completed_at,
                    allowed_actions=lifecycle.operation_allowed_actions(actor, task, o),
                )
                for o in sorted(task.operations, key=lambda o: (o.plot.field.number, o.plot.number))
            ],
            allowed_actions=lifecycle.allowed_actions(actor, task),
        )
        for task in tasks
    ]
