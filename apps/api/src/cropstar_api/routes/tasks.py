"""Tasks of a Farm. Thin: validation here, rules in the Task lifecycle and Access Policy."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, StringConstraints, field_validator
from sqlalchemy import case, nulls_last, select
from sqlalchemy.orm import Session as DbSession

from cropstar_api.db import Db
from cropstar_api.farms import FarmMembership
from cropstar_api.models import Membership, Priority, Task, TaskStatus, User
from cropstar_api.policy import Action, Actor
from cropstar_api.tasks.lifecycle import (
    ForbiddenError,
    InvalidAssigneeError,
    InvalidTransitionError,
    NewTask,
    TaskError,
    TaskLifecycle,
    TaskNotFoundError,
)
from cropstar_api.tasks.repository import SqlTaskRepository

router = APIRouter(prefix="/farms/{farm_id}", tags=["tasks"])

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]


# ── Schemas ─────────────────────────────────────────────────────────────────


class PersonOut(BaseModel):
    id: uuid.UUID
    email: str


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
    allowed_actions: list[Action]


class TaskCreate(BaseModel):
    title: Title
    description: Description | None = None
    due_date: date | None = None
    priority: Priority = Priority.NONE
    assignee_id: uuid.UUID | None = None
    done: bool = False

    @field_validator("description")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value or None


class TaskUpdate(BaseModel):
    """Only the fields sent are changed; send null to clear an optional field."""

    title: Title | None = None
    description: Description | None = None
    due_date: date | None = None
    priority: Priority | None = None
    assignee_id: uuid.UUID | None = None

    @field_validator("title", "priority")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("cannot be cleared")
        return value

    @field_validator("description")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value or None


# ── Routes ──────────────────────────────────────────────────────────────────


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
) -> list[TaskOut]:
    query = select(Task).where(Task.farm_id == membership.farm_id)
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
        task = _lifecycle(db).create(
            _actor(membership), membership.farm_id, NewTask(**body.model_dump())
        )
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
    except InvalidAssigneeError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error.code) from None
    except TaskError as error:  # pragma: no cover - every subclass is mapped above
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=error.code) from None


def _out(db: DbSession, membership: Membership, tasks: list[Task]) -> list[TaskOut]:
    people_ids = {
        person_id
        for task in tasks
        for person_id in (task.assignee_id, task.created_by_id, task.completed_by_id)
        if person_id is not None
    }
    people = (
        {
            user.id: PersonOut(id=user.id, email=user.email)
            for user in db.scalars(select(User).where(User.id.in_(people_ids)))
        }
        if people_ids
        else {}
    )
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
            assignee=people.get(task.assignee_id) if task.assignee_id else None,
            created_by=people.get(task.created_by_id) if task.created_by_id else None,
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_by=people.get(task.completed_by_id) if task.completed_by_id else None,
            completed_at=task.completed_at,
            allowed_actions=lifecycle.allowed_actions(actor, task),
        )
        for task in tasks
    ]
