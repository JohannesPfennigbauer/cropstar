import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from cropstar_api.models import FarmInput, FarmInputKind, FarmInputUnit, Role, Task, TaskStatus
from cropstar_api.operation_details import (
    FertilisationDetails,
    SowingDetails,
    TillageDetails,
    TillageImplement,
)
from cropstar_api.policy import Action
from cropstar_api.tasks.lifecycle import (
    DetailsTypeMismatchError,
    DetailsWithoutOperationTypeError,
    FarmInputKindError,
    FarmInputNotFoundError,
    ForbiddenError,
    InvalidTransitionError,
    NewTask,
    OperationDoneError,
    OperationFieldsError,
    OperationNeedsPlotsError,
    TaskLifecycle,
    UnitMismatchError,
    UnknownOperationTypeError,
)
from tests.test_task_lifecycle import FARM, Clock, InMemoryTasks, member

OPEN, DONE, DISCARDED = TaskStatus.OPEN, TaskStatus.DONE, TaskStatus.DISCARDED


def cultivate(depth: float) -> TillageDetails:
    return TillageDetails(implement=TillageImplement.CULTIVATOR, depth_cm=depth)


def stored(depth: float) -> dict[str, object]:
    """As `cultivate(depth)` is kept in the database."""
    return {"type": "tillage", "implement": "cultivator", "depth_cm": depth}


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
            plot_ids=frozenset(self.plots[n - 1].id for n in plots),
            **({"planned_details": cultivate(2)} | overrides),  # type: ignore[arg-type]
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
    assert [o.planned_details for o in task.operations] == [stored(2), stored(2)]
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
    assert (first.actual_details, first.performed_on) == (stored(2), s.clock.now.date())

    s.clock.now += timedelta(days=1)
    s.lifecycle.complete_operation(
        s.worker, FARM, task.id, s.op(task, 2), cultivate(3), date(2027, 3, 15)
    )
    second = next(o for o in task.operations if o.plot.number == 2)
    assert (second.actual_details, second.performed_on) == (stored(3), date(2027, 3, 15))
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
    s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1), cultivate(8))

    s.lifecycle.reopen_operation(s.worker, FARM, task.id, s.op(task, 1))
    operation = task.operations[0]
    assert (operation.status, operation.actual_details, operation.completed_at) == (
        OPEN,
        stored(8),
        None,
    )
    assert task.status is OPEN

    s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1))
    assert operation.actual_details == stored(8)


def test_discarding_and_restoring(s: Setup) -> None:
    task = s.harrow(1, 2)

    s.lifecycle.discard(s.worker, FARM, task.id)
    assert (task.status, s.statuses(task)) == (DISCARDED, [DISCARDED, DISCARDED])

    s.lifecycle.restore(s.worker, FARM, task.id)
    assert (task.status, s.statuses(task)) == (OPEN, [OPEN, OPEN])


def test_planned_details_can_differ_per_plot_and_follow_the_task_otherwise(s: Setup) -> None:
    task = s.harrow(1, 2, 3)
    s.lifecycle.edit_operation(
        s.worker, FARM, task.id, s.op(task, 2), {"planned_details": cultivate(1)}
    )
    s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 3))

    s.lifecycle.edit(s.worker, FARM, task.id, {"planned_details": cultivate(4)})

    planned = {o.plot.number: o.planned_details for o in task.operations}
    assert planned == {1: stored(4), 2: stored(1), 3: stored(2)}


def test_plots_join_any_time_but_done_operations_do_not_vanish(s: Setup) -> None:
    task = s.harrow(1, 2)
    s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1))
    plot = {n: s.plots[n - 1].id for n in (1, 2, 3)}

    s.lifecycle.edit(s.worker, FARM, task.id, {"plot_ids": [plot[1], plot[2], plot[3]]})
    assert s.statuses(task) == [DONE, OPEN, OPEN]
    assert task.operations[-1].planned_details == stored(2)

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

    s.lifecycle.edit_operation(
        s.advisor, FARM, task.id, s.op(task, 1), {"planned_details": cultivate(2)}
    )
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


def test_details_must_be_of_the_tasks_operation_type(s: Setup) -> None:
    task = s.harrow(1)
    slurry = FertilisationDetails(amount=20, unit="m3_per_ha")

    with pytest.raises(DetailsTypeMismatchError):
        s.lifecycle.edit(s.worker, FARM, task.id, {"planned_details": slurry})
    with pytest.raises(DetailsTypeMismatchError):
        s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1), slurry)
    with pytest.raises(DetailsTypeMismatchError):
        s.harrow(1, planned_details=slurry)


def test_general_tasks_have_no_planned_details(s: Setup) -> None:
    with pytest.raises(DetailsWithoutOperationTypeError):
        s.lifecycle.create(s.worker, FARM, NewTask("Zaun", planned_details=cultivate(2)))


def _input(s: Setup, kind: FarmInputKind, unit: FarmInputUnit | None = None) -> FarmInput:
    item = FarmInput(id=uuid.uuid4(), farm_id=FARM, kind=kind, name=str(kind), unit=unit)
    s.repo.inputs.append(item)
    return item


def _sow(s: Setup, details: SowingDetails) -> Task:
    new = NewTask(
        "Säen",
        operation_type="sowing",
        plot_ids=frozenset({s.plots[0].id}),
        planned_details=details,
    )
    return s.lifecycle.create(s.worker, FARM, new)


def test_sowing_refers_to_seed_of_the_farm(s: Setup) -> None:
    seed = _input(s, FarmInputKind.SEED)
    slurry = _input(s, FarmInputKind.FERTILISER, FarmInputUnit.CUBIC_METRE)

    task = _sow(s, SowingDetails(farm_input_id=seed.id))

    assert task.planned_details == {"type": "sowing", "farm_input_id": str(seed.id)}
    with pytest.raises(FarmInputKindError):
        _sow(s, SowingDetails(farm_input_id=slurry.id))
    with pytest.raises(FarmInputNotFoundError):
        _sow(s, SowingDetails(farm_input_id=uuid.uuid4()))


def test_fertilisation_amounts_must_fit_the_inputs_unit(s: Setup) -> None:
    slurry = _input(s, FarmInputKind.FERTILISER, FarmInputUnit.CUBIC_METRE)
    task = s.lifecycle.create(
        s.worker,
        FARM,
        NewTask("Gülle", operation_type="fertilisation", plot_ids=frozenset({s.plots[0].id})),
    )
    by_volume = FertilisationDetails(farm_input_id=slurry.id, amount=20, unit="m3_per_ha")
    by_mass = FertilisationDetails(farm_input_id=slurry.id, amount=20, unit="t_per_ha")

    s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1), by_volume)
    s.lifecycle.reopen_operation(s.worker, FARM, task.id, s.op(task, 1))
    with pytest.raises(UnitMismatchError):
        s.lifecycle.complete_operation(s.worker, FARM, task.id, s.op(task, 1), by_mass)
