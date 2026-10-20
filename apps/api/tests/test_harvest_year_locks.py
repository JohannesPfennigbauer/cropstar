from collections.abc import Callable

import pytest

from cropstar_api.models import Role, Task
from cropstar_api.policy import Action, Denial
from cropstar_api.tasks.lifecycle import ForbiddenError, NewTask, TaskLifecycle
from tests.test_operations import Setup
from tests.test_task_lifecycle import FARM, member


class Locks(Setup):
    def __init__(self) -> None:
        super().__init__()
        self.admin = member(self.repo, Role.ADMIN)
        other_year = self.repo.add_field(FARM, 2028, 1)
        self.next_year_plot = self.repo.add_plot(other_year, 1)

    def lock(self, year: int) -> None:
        self.repo.locks.add((FARM, year))
        # A lock takes effect with the next request, which builds a fresh lifecycle.
        self.lifecycle = TaskLifecycle(self.repo, self.clock)


@pytest.fixture
def s() -> Locks:
    return Locks()


def _refused(call: Callable[[], object]) -> None:
    with pytest.raises(ForbiddenError) as refused:
        call()
    assert refused.value.code == Denial.LOCKED


def test_every_write_to_a_task_of_a_locked_year_is_refused(s: Locks) -> None:
    task = s.harrow(1, 2)
    done = s.harrow(1)
    s.lifecycle.complete_operation(s.worker, FARM, done.id, s.op(done, 1))
    s.lock(2027)
    life, admin = s.lifecycle, s.admin

    _refused(lambda: life.edit(admin, FARM, task.id, {"title": "Später"}))
    _refused(lambda: life.edit(admin, FARM, task.id, {"plot_ids": [s.plots[0].id]}))
    _refused(lambda: life.complete(admin, FARM, task.id))
    _refused(lambda: life.discard(admin, FARM, task.id))
    _refused(lambda: life.reopen(admin, FARM, done.id))
    _refused(lambda: life.delete(admin, FARM, task.id))
    _refused(lambda: life.complete_operation(admin, FARM, task.id, s.op(task, 1)))
    _refused(lambda: life.discard_operation(admin, FARM, task.id, s.op(task, 1)))
    _refused(lambda: life.reopen_operation(admin, FARM, done.id, s.op(done, 1)))
    _refused(
        lambda: life.edit_operation(admin, FARM, task.id, s.op(task, 1), {"actual_details": "x"})
    )


def test_a_locked_year_offers_no_actions_but_stays_readable(s: Locks) -> None:
    task = s.harrow(1)
    s.lock(2027)

    assert s.lifecycle.allowed_actions(s.admin, task) == []
    assert s.lifecycle.operation_allowed_actions(s.admin, task, task.operations[0]) == []


def test_no_task_can_be_created_on_or_moved_into_a_locked_year(s: Locks) -> None:
    elsewhere = s.lifecycle.create(
        s.worker, FARM, NewTask("Bodenprobe", plot_ids=frozenset({s.next_year_plot.id}))
    )
    s.lock(2027)

    _refused(
        lambda: s.lifecycle.create(
            s.worker, FARM, NewTask("Bodenprobe", plot_ids=frozenset({s.plots[0].id}))
        )
    )
    _refused(lambda: s.harrow(1))
    _refused(lambda: s.lifecycle.edit(s.worker, FARM, elsewhere.id, {"plot_ids": [s.plots[0].id]}))
    assert [p.id for p in elsewhere.plots] == [s.next_year_plot.id]


def test_tasks_without_areas_and_other_years_are_unaffected(s: Locks) -> None:
    general = s.lifecycle.create(s.worker, FARM, NewTask("Traktor-Service"))
    other: Task = s.lifecycle.create(
        s.worker, FARM, NewTask("Bodenprobe", plot_ids=frozenset({s.next_year_plot.id}))
    )
    s.lock(2027)

    s.lifecycle.edit(s.worker, FARM, general.id, {"title": "Traktor-Service 2027"})
    s.lifecycle.complete(s.worker, FARM, general.id)
    s.lifecycle.complete(s.worker, FARM, other.id)
    assert Action.EDIT_TASK in s.lifecycle.allowed_actions(s.worker, other)
    s.lifecycle.delete(s.admin, FARM, general.id)


def test_unlocking_makes_the_year_editable_again(s: Locks) -> None:
    task = s.harrow(1)
    s.lock(2027)
    s.repo.locks.clear()
    s.lifecycle = TaskLifecycle(s.repo, s.clock)

    s.lifecycle.edit(s.worker, FARM, task.id, {"title": "Striegeln, zweiter Durchgang"})
    assert task.title == "Striegeln, zweiter Durchgang"
