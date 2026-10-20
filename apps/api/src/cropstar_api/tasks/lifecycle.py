"""The Task lifecycle: every change to a Task or its Operations goes through here.

Order of checks for each command: the Task exists on this Farm, the Access Policy allows the
actor this action, the Status allows the transition, and the rest of the input is valid.

A Task with an Operation Type holds one Operation per Plot. Its Status is derived from them:
Open while any Operation is Open, Discarded when all are Discarded, otherwise Done.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

from cropstar_api.models import Field, Operation, Plot, Priority, Role, Task, TaskStatus
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

    def operation_type_exists(self, code: str) -> bool: ...


class TaskError(Exception):
    code = "task_error"


class TaskNotFoundError(TaskError):
    code = "task_not_found"


class OperationNotFoundError(TaskError):
    code = "operation_not_found"


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


class UnknownOperationTypeError(TaskError):
    code = "unknown_operation_type"


class OperationNeedsPlotsError(TaskError):
    """An Operation always concerns exactly one Plot, so its Task needs at least one."""

    code = "operation_needs_plots"


class OperationFieldsError(TaskError):
    code = "operation_fields_not_allowed"


class OperationDoneError(TaskError):
    """Removing a Plot whose Operation is Done would silently shrink the Operation Log."""

    code = "operation_done"


@dataclass(frozen=True)
class NewTask:
    title: str
    description: str | None = None
    due_date: date | None = None
    priority: Priority = Priority.NONE
    assignee_id: uuid.UUID | None = None
    # Recording work after the fact creates the Task (and its Operations) as Done.
    done: bool = False
    field_ids: frozenset[uuid.UUID] = frozenset()
    plot_ids: frozenset[uuid.UUID] = frozenset()
    operation_type: str | None = None
    planned_details: str | None = None


EDITABLE_FIELDS = frozenset(
    {
        "title",
        "description",
        "due_date",
        "priority",
        "assignee_id",
        "field_ids",
        "plot_ids",
        "planned_details",
    }
)
EDITABLE_OPERATION_FIELDS = frozenset({"planned_details", "actual_details", "performed_on"})

# Which Status each status-changing action starts from and leads to.
_TRANSITIONS: dict[Action, tuple[TaskStatus, TaskStatus]] = {
    Action.COMPLETE_TASK: (TaskStatus.OPEN, TaskStatus.DONE),
    Action.REOPEN_TASK: (TaskStatus.DONE, TaskStatus.OPEN),
    Action.DISCARD_TASK: (TaskStatus.OPEN, TaskStatus.DISCARDED),
    Action.RESTORE_TASK: (TaskStatus.DISCARDED, TaskStatus.OPEN),
}
OPERATION_ACTIONS = (Action.EDIT_TASK, *_TRANSITIONS)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def facts(task: Task) -> TaskFacts:
    # Nothing is locked yet; Locked Harvest Years arrive with their own issue.
    return TaskFacts(created_by=task.created_by_id)


class TaskLifecycle:
    def __init__(self, repository: TaskRepository, clock: Callable[[], datetime] = _utcnow):
        self._repository = repository
        self._clock = clock

    # ── Tasks ───────────────────────────────────────────────────────────────

    def create(self, actor: Actor, farm_id: uuid.UUID, new: NewTask) -> Task:
        self._require(actor, Action.CREATE_TASK, None)
        if new.done:
            self._require(actor, Action.COMPLETE_TASK, None)
        if new.operation_type is not None:
            if not self._repository.operation_type_exists(new.operation_type):
                raise UnknownOperationTypeError(new.operation_type)
            self._check_operation_areas(new.field_ids, new.plot_ids)
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
            status=TaskStatus.OPEN,
            created_by_id=actor.user_id,
            created_at=now,
            updated_at=now,
            operation_type=new.operation_type,
            planned_details=new.planned_details,
        )
        task.operations = []
        self._set_areas(task, new.field_ids, new.plot_ids)
        if task.operation_type is None:
            if new.done:
                self._mark_done(task, actor, now)
        else:
            for operation in task.operations:
                if new.done:
                    self._complete(operation, actor, now, None, new.due_date)
            self._derive_status(task)
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
            field_ids = frozenset(changes.get("field_ids", {f.id for f in task.fields}))
            plot_ids = frozenset(changes.get("plot_ids", {p.id for p in task.plots}))
            if task.operation_type is not None:
                self._check_operation_areas(field_ids, plot_ids)
            self._set_areas(task, field_ids, plot_ids)
        if "planned_details" in changes and task.operation_type is not None:
            # Open Operations follow the Task's plan unless they were adjusted on their own.
            for operation in task.operations:
                if (
                    operation.status is TaskStatus.OPEN
                    and operation.planned_details == task.planned_details
                ):
                    operation.planned_details = changes["planned_details"]
        for name, value in changes.items():
            if name not in ("field_ids", "plot_ids"):
                setattr(task, name, value)
        if task.operation_type is not None:
            self._derive_status(task)
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
            if decide(actor, action, facts(task)) and self._can_transition(task, action)
        ]

    # ── Operations ──────────────────────────────────────────────────────────

    def complete_operation(
        self,
        actor: Actor,
        farm_id: uuid.UUID,
        task_id: uuid.UUID,
        operation_id: uuid.UUID,
        actual_details: str | None = None,
        performed_on: date | None = None,
    ) -> Task:
        """Done, with Actual Details defaulting to the draft, else to the Planned Details."""
        task, operation = self._operation(
            actor, farm_id, task_id, operation_id, Action.COMPLETE_TASK
        )
        self._complete(operation, actor, self._clock(), actual_details, performed_on)
        return self._touch(task)

    def reopen_operation(
        self, actor: Actor, farm_id: uuid.UUID, task_id: uuid.UUID, operation_id: uuid.UUID
    ) -> Task:
        task, operation = self._operation(actor, farm_id, task_id, operation_id, Action.REOPEN_TASK)
        operation.status = TaskStatus.OPEN
        operation.completed_by_id = None
        operation.completed_at = None
        return self._touch(task)

    def discard_operation(
        self, actor: Actor, farm_id: uuid.UUID, task_id: uuid.UUID, operation_id: uuid.UUID
    ) -> Task:
        task, operation = self._operation(
            actor, farm_id, task_id, operation_id, Action.DISCARD_TASK
        )
        operation.status = TaskStatus.DISCARDED
        return self._touch(task)

    def restore_operation(
        self, actor: Actor, farm_id: uuid.UUID, task_id: uuid.UUID, operation_id: uuid.UUID
    ) -> Task:
        task, operation = self._operation(
            actor, farm_id, task_id, operation_id, Action.RESTORE_TASK
        )
        operation.status = TaskStatus.OPEN
        return self._touch(task)

    def edit_operation(
        self,
        actor: Actor,
        farm_id: uuid.UUID,
        task_id: uuid.UUID,
        operation_id: uuid.UUID,
        changes: dict[str, Any],
    ) -> Task:
        unknown = set(changes) - EDITABLE_OPERATION_FIELDS
        if unknown:
            raise ValueError(f"Not editable: {sorted(unknown)}")
        task, operation = self._operation(actor, farm_id, task_id, operation_id, Action.EDIT_TASK)
        for name, value in changes.items():
            setattr(operation, name, value)
        return self._touch(task)

    def operation_allowed_actions(
        self, actor: Actor, task: Task, operation: Operation
    ) -> list[Action]:
        return [
            action
            for action in OPERATION_ACTIONS
            if decide(actor, action, facts(task))
            and (action not in _TRANSITIONS or _TRANSITIONS[action][0] is operation.status)
        ]

    # ── Internals ───────────────────────────────────────────────────────────

    def _transition(
        self, actor: Actor, farm_id: uuid.UUID, task_id: uuid.UUID, action: Action
    ) -> Task:
        task = self._get(farm_id, task_id)
        self._require(actor, action, task)
        if not self._can_transition(task, action):
            raise InvalidTransitionError(f"{action} is not possible from {task.status}")
        now = self._clock()
        if task.operation_type is None:
            source, target = _TRANSITIONS[action]
            task.status = target
            if target is TaskStatus.DONE:
                self._mark_done(task, actor, now)
            elif action is Action.REOPEN_TASK:
                task.completed_by_id = None
                task.completed_at = None
        else:
            # On a Task with Operations, the action applies to every Operation it fits.
            source, target = _TRANSITIONS[action]
            for operation in task.operations:
                if operation.status is not source:
                    continue
                if target is TaskStatus.DONE:
                    self._complete(operation, actor, now, None, None)
                else:
                    operation.status = target
                    if action is Action.REOPEN_TASK:
                        operation.completed_by_id = None
                        operation.completed_at = None
            self._derive_status(task)
        task.updated_at = now
        return task

    def _can_transition(self, task: Task, action: Action) -> bool:
        if action not in _TRANSITIONS:
            return True
        source, _ = _TRANSITIONS[action]
        if task.operation_type is None:
            return task.status is source
        statuses = {operation.status for operation in task.operations}
        if action is Action.COMPLETE_TASK or action is Action.RESTORE_TASK:
            return source in statuses
        # Reopen a Done Task; discard an Open one. Both act on the matching Operations.
        return task.status is source

    def _complete(
        self,
        operation: Operation,
        actor: Actor,
        now: datetime,
        actual_details: str | None,
        performed_on: date | None,
    ) -> None:
        operation.status = TaskStatus.DONE
        operation.actual_details = (
            actual_details or operation.actual_details or operation.planned_details
        )
        operation.performed_on = performed_on or operation.performed_on or now.date()
        operation.completed_by_id = actor.user_id
        operation.completed_at = now

    def _mark_done(self, task: Task, actor: Actor, now: datetime) -> None:
        task.status = TaskStatus.DONE
        task.completed_by_id = actor.user_id
        task.completed_at = now

    def _derive_status(self, task: Task) -> None:
        statuses = {operation.status for operation in task.operations}
        if TaskStatus.OPEN in statuses:
            task.status = TaskStatus.OPEN
        elif statuses == {TaskStatus.DISCARDED}:
            task.status = TaskStatus.DISCARDED
        else:
            task.status = TaskStatus.DONE
        done = [o for o in task.operations if o.status is TaskStatus.DONE and o.completed_at]
        if task.status is TaskStatus.DONE and done:
            latest = max(done, key=lambda o: o.completed_at or datetime.min.replace(tzinfo=UTC))
            task.completed_by_id = latest.completed_by_id
            task.completed_at = latest.completed_at
        else:
            task.completed_by_id = None
            task.completed_at = None

    def _touch(self, task: Task) -> Task:
        self._derive_status(task)
        task.updated_at = self._clock()
        return task

    def _operation(
        self,
        actor: Actor,
        farm_id: uuid.UUID,
        task_id: uuid.UUID,
        operation_id: uuid.UUID,
        action: Action,
    ) -> tuple[Task, Operation]:
        task = self._get(farm_id, task_id)
        operation = next((o for o in task.operations if o.id == operation_id), None)
        if operation is None:
            raise OperationNotFoundError(str(operation_id))
        self._require(actor, action, task)
        if action in _TRANSITIONS and operation.status is not _TRANSITIONS[action][0]:
            raise InvalidTransitionError(f"{action} is not possible from {operation.status}")
        return task, operation

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

    def _check_operation_areas(
        self, field_ids: frozenset[uuid.UUID], plot_ids: frozenset[uuid.UUID]
    ) -> None:
        if field_ids:
            raise OperationFieldsError("Operations concern Plots only")
        if not plot_ids:
            raise OperationNeedsPlotsError("an Operation needs a Plot")

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
        if task.operation_type is not None:
            self._sync_operations(task, plots)
        task.fields = sorted(fields, key=lambda field: field.number)
        task.plots = sorted(plots, key=lambda plot: (plot.field.number, plot.number))
        task.harvest_year = years.pop() if years else None

    def _sync_operations(self, task: Task, plots: list[Plot]) -> None:
        """One Operation per Plot: new Plots get an Open one, removed Plots lose theirs."""
        wanted = {plot.id for plot in plots}
        removed = [o for o in task.operations if o.plot_id not in wanted]
        if any(o.status is TaskStatus.DONE for o in removed):
            raise OperationDoneError("reopen a Done Operation before removing its Plot")
        for operation in removed:
            task.operations.remove(operation)
        present = {o.plot_id for o in task.operations}
        for plot in plots:
            if plot.id not in present:
                task.operations.append(
                    Operation(
                        id=uuid.uuid4(),
                        task_id=task.id,
                        plot_id=plot.id,
                        plot=plot,
                        status=TaskStatus.OPEN,
                        planned_details=task.planned_details,
                    )
                )

    def _check_assignee(self, farm_id: uuid.UUID, assignee_id: uuid.UUID | None) -> None:
        if assignee_id is None:
            return
        role = self._repository.role_of(farm_id, assignee_id)
        if role is None or not can_be_assigned(role):
            raise InvalidAssigneeError(str(assignee_id))
