import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from cropstar_api.models import Role, Task, TaskStatus
from cropstar_api.policy import Action
from cropstar_api.tasks.lifecycle import (
    ForbiddenError,
    InvalidTransitionError,
    NewTask,
    OperationDoneError,
    OperationFieldsError,
    OperationNeedsPlotsError,
    TaskLifecycle,
    UnknownOperationTypeError,
)
from tests.test_task_lifecycle import FARM, Clock, InMemoryTasks, member

OPEN, DONE, DISCARDED = TaskStatus.OPEN, TaskStatus.DONE, TaskStatus.DISCARDED


class Setup:
    def __init__(self) -> None:
        self.repo = InMemoryTasks()
        self.clock = Clock()
        self.lifecycle = TaskLifecycle(self.repo, self.clock)
        self.worker = member(self.repo, Role.WORKER)
        self.advisor = member(self.repo, Role.ADVISOR)
        field = self.repo.add_field(FARM, 2027, 1)
        self.plots = [self.repo.add_plot(field, n) for n in (1, 2, 3)]

    def harrow(self, *plots: int, **overrides: object) -> Task:
        new = NewTask(
            "Striegeln",
            operation_type="tillage",
            planned_details="Striegel, 2 cm",
            plot_ids=frozenset(self.plots[n - 1].id for n in plots),
            **overrides,  # type: ignore[arg-type]
        )
        return self.lifecycle.create(self.worker, FARM, new)

    def statuses(self, task: Task) -> list[TaskStatus]:
        return [o.status for o in sorted(task.operations, key=lambda o: o.plot.number)]

    def op(self, task: Task, plot: int) -> uuid.UUID:
        return next(o.id for o in task.operations if o.plot.number == plot)


@pytest.fixture
def s() -> Setup:
    return Setup()


def test_an_operation_task_holds_one_operation_per_plot(s: Setup) -> None:
    task = s.harrow(1, 2)

    assert task.status is OPEN
    assert task.harvest_year == 2027
    assert sorted(o.plot.number for o in task.operations) == [1, 2]
    assert {o.planned_details for o in task.operations} == {"Striegel, 2 cm"}
    assert s.statuses(task) == [OPEN, OPEN]


def test_operations_concern_plots_only(s: Setup) -> None:
    field = s.repo.all_fields[0]

    with pytest.raises(OperationNeedsPlotsError):
        s.lifecycle.create(s.worker, FARM, NewTask("Säen", operation_type="sowing"))
    with pytest.raises(OperationFieldsError):
        s.lifecycle.create(
            s.worker,
            FARM,
            NewTask(
                "Säen",
                operation_type="sowing",
                field_ids=frozenset({field.id}),
                plot_ids=frozenset({s.plots[0].id}),
            ),
        )
    with pytest.raises(UnknownOperationTypeError):
        s.lifecycle.create(
            s.worker,
            FARM,
            NewTask("Spritzen", operation_type="spraying", plot_ids=frozenset({s.plots[0].id})),
        )


def test_partial_completion_and_derived_status(s: Setup) -> None:
    task = s.harrow(1, 2)

    s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1))
    assert s.statuses(task) == [DONE, OPEN]
    assert task.status is OPEN
    first = next(o for o in task.operations if o.plot.number == 1)
    assert (first.actual_details, first.performed_on) == ("Striegel, 2 cm", s.clock.now.date())

    s.clock.now += timedelta(days=1)
    s.lifecycle.complete_operation(
        s.worker, FARM, task.id, s.op(task, 2), "Striegel, 3 cm", date(2027, 3, 15)
    )
    second = next(o for o in task.operations if o.plot.number == 2)
    assert (second.actual_details, second.performed_on) == ("Striegel, 3 cm", date(2027, 3, 15))
    assert task.status is DONE
    assert task.completed_at == s.clock.now


def test_completing_the_task_completes_every_open_operation(s: Setup) -> None:
    task = s.harrow(1, 2, 3)
    s.lifecycle.discard_operation(s.worker, FARM, task.id, s.op(task, 3))

    s.lifecycle.complete(s.worker, FARM, task.id)

    assert s.statuses(task) == [DONE, DONE, DISCARDED]
    assert task.status is DONE


def test_reopening_keeps_actual_details_as_a_draft(s: Setup) -> None:
    task = s.harrow(1)
    s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1), "40 kg N")

    s.lifecycle.reopen_operation(s.worker, FARM, task.id, s.op(task, 1))
    operation = task.operations[0]
    assert (operation.status, operation.actual_details, operation.completed_at) == (
        OPEN,
        "40 kg N",
        None,
    )
    assert task.status is OPEN

    s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1))
    assert operation.actual_details == "40 kg N"


def test_discarding_and_restoring(s: Setup) -> None:
    task = s.harrow(1, 2)

    s.lifecycle.discard(s.worker, FARM, task.id)
    assert (task.status, s.statuses(task)) == (DISCARDED, [DISCARDED, DISCARDED])

    s.lifecycle.restore(s.worker, FARM, task.id)
    assert (task.status, s.statuses(task)) == (OPEN, [OPEN, OPEN])


def test_planned_details_can_differ_per_plot_and_follow_the_task_otherwise(s: Setup) -> None:
    task = s.harrow(1, 2, 3)
    s.lifecycle.edit_operation(s.worker, FARM, task.id, s.op(task, 2), {"planned_details": "1 cm"})
    s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 3))

    s.lifecycle.edit(s.worker, FARM, task.id, {"planned_details": "Striegel, 4 cm"})

    planned = {o.plot.number: o.planned_details for o in task.operations}
    assert planned == {1: "Striegel, 4 cm", 2: "1 cm", 3: "Striegel, 2 cm"}


def test_plots_join_any_time_but_done_operations_do_not_vanish(s: Setup) -> None:
    task = s.harrow(1, 2)
    s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1))
    plot = {n: s.plots[n - 1].id for n in (1, 2, 3)}

    s.lifecycle.edit(s.worker, FARM, task.id, {"plot_ids": [plot[1], plot[2], plot[3]]})
    assert s.statuses(task) == [DONE, OPEN, OPEN]
    assert task.operations[-1].planned_details == "Striegel, 2 cm"

    s.lifecycle.edit(s.worker, FARM, task.id, {"plot_ids": [plot[1], plot[3]]})
    assert sorted(o.plot.number for o in task.operations) == [1, 3]

    with pytest.raises(OperationDoneError):
        s.lifecycle.edit(s.worker, FARM, task.id, {"plot_ids": [plot[3]]})

    s.lifecycle.reopen_operation(s.worker, FARM, task.id, s.op(task, 1))
    s.lifecycle.edit(s.worker, FARM, task.id, {"plot_ids": [plot[3]]})
    assert [o.plot.number for o in task.operations] == [3]
    with pytest.raises(OperationNeedsPlotsError):
        s.lifecycle.edit(s.worker, FARM, task.id, {"plot_ids": []})


def test_recording_after_the_fact_completes_every_operation_on_the_due_date(s: Setup) -> None:
    task = s.harrow(1, 2, done=True, due_date=date(2027, 3, 1))

    assert task.status is DONE
    assert {(o.status, o.performed_on) for o in task.operations} == {(DONE, date(2027, 3, 1))}


def test_advisors_adjust_plans_but_do_not_record_work(s: Setup) -> None:
    task = s.harrow(1)

    s.lifecycle.edit_operation(s.advisor, FARM, task.id, s.op(task, 1), {"planned_details": "2 cm"})
    with pytest.raises(ForbiddenError):
        s.lifecycle.complete_operation(s.advisor, FARM, task.id, s.op(task, 1))


def test_operation_transitions_only_from_their_status(s: Setup) -> None:
    task = s.harrow(1)

    with pytest.raises(InvalidTransitionError):
        s.lifecycle.reopen_operation(s.worker, FARM, task.id, s.op(task, 1))
    s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1))
    with pytest.raises(InvalidTransitionError):
        s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1))


def test_allowed_actions_on_operations_and_their_task(s: Setup) -> None:
    task = s.harrow(1, 2)
    s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1))
    done, still_open = sorted(task.operations, key=lambda o: o.plot.number)

    assert s.lifecycle.operation_allowed_actions(s.worker, task, done) == [
        Action.EDIT_TASK,
        Action.REOPEN_TASK,
    ]
    assert s.lifecycle.operation_allowed_actions(s.worker, task, still_open) == [
        Action.EDIT_TASK,
        Action.COMPLETE_TASK,
        Action.DISCARD_TASK,
    ]
    assert s.lifecycle.allowed_actions(s.worker, task) == [
        Action.EDIT_TASK,
        Action.COMPLETE_TASK,
        Action.DISCARD_TASK,
        Action.DELETE_TASK,
    ]
    assert s.lifecycle.operation_allowed_actions(s.advisor, task, still_open) == [Action.EDIT_TASK]


def test_plain_tasks_are_unaffected(s: Setup) -> None:
    task = s.lifecycle.create(s.worker, FARM, NewTask("Traktor-Service"))

    s.lifecycle.complete(s.worker, FARM, task.id)

    assert (task.status, task.operations) == (DONE, [])
    assert task.completed_at == datetime(2027, 3, 15, 7, 30, tzinfo=UTC)
