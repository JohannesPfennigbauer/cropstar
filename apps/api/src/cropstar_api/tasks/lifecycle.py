"""The Task lifecycle: every change to a Task goes through here.

Order of checks for each command: the Task exists on this Farm, the Access Policy allows the
actor this action, the Status allows the transition, and any assignee may be assigned.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

from cropstar_api.models import Field, Plot, Priority, Role, Task, TaskStatus
from cropstar_api.policy import (
    TASK_ACTIONS,
    Action,
    Actor,
    Denial,
    TaskFacts,
    can_be_assigned,
    decide,
)


class TaskRepository(Protocol):
    def get(self, farm_id: uuid.UUID, task_id: uuid.UUID) -> Task | None: ...

    def add(self, task: Task) -> None: ...

    def delete(self, task: Task) -> None: ...

    def role_of(self, farm_id: uuid.UUID, user_id: uuid.UUID) -> Role | None: ...

    def fields(self, farm_id: uuid.UUID, ids: frozenset[uuid.UUID]) -> list[Field]: ...

    def plots(self, farm_id: uuid.UUID, ids: frozenset[uuid.UUID]) -> list[Plot]:
        """The Plots among `ids` that belong to the Farm, each with its Field loaded."""
        ...


class TaskError(Exception):
    code = "task_error"


class TaskNotFoundError(TaskError):
    code = "task_not_found"


class ForbiddenError(TaskError):
    def __init__(self, denial: Denial) -> None:
        super().__init__(denial.value)
        self.code = denial.value


class InvalidTransitionError(TaskError):
    code = "invalid_transition"


class InvalidAssigneeError(TaskError):
    code = "invalid_assignee"


class AreaNotFoundError(TaskError):
    code = "area_not_found"


class MixedHarvestYearsError(TaskError):
    """A Task's Fields and Plots must all belong to one Harvest Year."""

    code = "mixed_harvest_years"


@dataclass(frozen=True)
class NewTask:
    title: str
    description: str | None = None
    due_date: date | None = None
    priority: Priority = Priority.NONE
    assignee_id: uuid.UUID | None = None
    # Recording work after the fact creates the Task as Done.
    done: bool = False
    field_ids: frozenset[uuid.UUID] = frozenset()
    plot_ids: frozenset[uuid.UUID] = frozenset()


EDITABLE_FIELDS = frozenset(
    {"title", "description", "due_date", "priority", "assignee_id", "field_ids", "plot_ids"}
)

# Which Status each status-changing action starts from and leads to.
_TRANSITIONS: dict[Action, tuple[TaskStatus, TaskStatus]] = {
    Action.COMPLETE_TASK: (TaskStatus.OPEN, TaskStatus.DONE),
    Action.REOPEN_TASK: (TaskStatus.DONE, TaskStatus.OPEN),
    Action.DISCARD_TASK: (TaskStatus.OPEN, TaskStatus.DISCARDED),
    Action.RESTORE_TASK: (TaskStatus.DISCARDED, TaskStatus.OPEN),
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def facts(task: Task) -> TaskFacts:
    # Tasks have no Fields or Plots yet, so no Harvest Year and nothing to lock.
    return TaskFacts(created_by=task.created_by_id)


class TaskLifecycle:
    def __init__(self, repository: TaskRepository, clock: Callable[[], datetime] = _utcnow):
        self._repository = repository
        self._clock = clock

    def create(self, actor: Actor, farm_id: uuid.UUID, new: NewTask) -> Task:
        self._require(actor, Action.CREATE_TASK, None)
        if new.done:
            self._require(actor, Action.COMPLETE_TASK, None)
        self._check_assignee(farm_id, new.assignee_id)
        now = self._clock()
        task = Task(
            id=uuid.uuid4(),
            farm_id=farm_id,
            title=new.title,
            description=new.description,
            due_date=new.due_date,
            priority=new.priority,
            assignee_id=new.assignee_id,
            status=TaskStatus.DONE if new.done else TaskStatus.OPEN,
            created_by_id=actor.user_id,
            created_at=now,
            updated_at=now,
            completed_by_id=actor.user_id if new.done else None,
            completed_at=now if new.done else None,
        )
        self._set_areas(task, new.field_ids, new.plot_ids)
        self._repository.add(task)
        return task

    def edit(
        self, actor: Actor, farm_id: uuid.UUID, task_id: uuid.UUID, changes: dict[str, Any]
    ) -> Task:
        unknown = set(changes) - EDITABLE_FIELDS
        if unknown:
            raise ValueError(f"Not editable: {sorted(unknown)}")
        task = self._get(farm_id, task_id)
        self._require(actor, Action.EDIT_TASK, task)
        if "assignee_id" in changes:
            self._check_assignee(farm_id, changes["assignee_id"])
        if "field_ids" in changes or "plot_ids" in changes:
            self._set_areas(
                task,
                frozenset(changes.get("field_ids", {f.id for f in task.fields})),
                frozenset(changes.get("plot_ids", {p.id for p in task.plots})),
            )
        for name, value in changes.items():
            if name not in ("field_ids", "plot_ids"):
                setattr(task, name, value)
        task.updated_at = self._clock()
        return task

    def complete(self, actor: Actor, farm_id: uuid.UUID, task_id: uuid.UUID) -> Task:
        return self._transition(actor, farm_id, task_id, Action.COMPLETE_TASK)

    def reopen(self, actor: Actor, farm_id: uuid.UUID, task_id: uuid.UUID) -> Task:
        return self._transition(actor, farm_id, task_id, Action.REOPEN_TASK)

    def discard(self, actor: Actor, farm_id: uuid.UUID, task_id: uuid.UUID) -> Task:
        return self._transition(actor, farm_id, task_id, Action.DISCARD_TASK)

    def restore(self, actor: Actor, farm_id: uuid.UUID, task_id: uuid.UUID) -> Task:
        return self._transition(actor, farm_id, task_id, Action.RESTORE_TASK)

    def delete(self, actor: Actor, farm_id: uuid.UUID, task_id: uuid.UUID) -> None:
        task = self._get(farm_id, task_id)
        self._require(actor, Action.DELETE_TASK, task)
        self._repository.delete(task)

    def allowed_actions(self, actor: Actor, task: Task) -> list[Action]:
        """What `actor` can do with `task` right now: permitted and valid from its Status."""
        return [
            action
            for action in TASK_ACTIONS
            if decide(actor, action, facts(task))
            and (action not in _TRANSITIONS or _TRANSITIONS[action][0] is task.status)
        ]

    # ── Internals ───────────────────────────────────────────────────────────

    def _transition(
        self, actor: Actor, farm_id: uuid.UUID, task_id: uuid.UUID, action: Action
    ) -> Task:
        task = self._get(farm_id, task_id)
        self._require(actor, action, task)
        source, target = _TRANSITIONS[action]
        if task.status is not source:
            raise InvalidTransitionError(f"{action} needs {source}, task is {task.status}")
        now = self._clock()
        task.status = target
        if target is TaskStatus.DONE:
            task.completed_by_id = actor.user_id
            task.completed_at = now
        elif action is Action.REOPEN_TASK:
            task.completed_by_id = None
            task.completed_at = None
        task.updated_at = now
        return task

    def _get(self, farm_id: uuid.UUID, task_id: uuid.UUID) -> Task:
        task = self._repository.get(farm_id, task_id)
        if task is None:
            raise TaskNotFoundError(str(task_id))
        return task

    def _require(self, actor: Actor, action: Action, task: Task | None) -> None:
        decision = decide(actor, action, facts(task) if task else None)
        if not decision:
            assert decision.denial is not None
            raise ForbiddenError(decision.denial)

    def _set_areas(
        self, task: Task, field_ids: frozenset[uuid.UUID], plot_ids: frozenset[uuid.UUID]
    ) -> None:
        fields = self._repository.fields(task.farm_id, field_ids) if field_ids else []
        plots = self._repository.plots(task.farm_id, plot_ids) if plot_ids else []
        if len(fields) != len(field_ids) or len(plots) != len(plot_ids):
            raise AreaNotFoundError("unknown Field or Plot for this Farm")
        years = {field.harvest_year for field in fields} | {
            plot.field.harvest_year for plot in plots
        }
        if len(years) > 1:
            raise MixedHarvestYearsError(f"Harvest Years {sorted(years)}")
        task.fields = sorted(fields, key=lambda field: field.number)
        task.plots = sorted(plots, key=lambda plot: (plot.field.number, plot.number))
        task.harvest_year = years.pop() if years else None

    def _check_assignee(self, farm_id: uuid.UUID, assignee_id: uuid.UUID | None) -> None:
        if assignee_id is None:
            return
        role = self._repository.role_of(farm_id, assignee_id)
        if role is None or not can_be_assigned(role):
            raise InvalidAssigneeError(str(assignee_id))
