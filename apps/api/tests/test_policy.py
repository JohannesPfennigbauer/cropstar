import uuid

import pytest

from cropstar_api.models import Role
from cropstar_api.policy import (
    Action,
    Actor,
    Denial,
    TaskFacts,
    can_be_assigned,
    decide,
)

ME = uuid.uuid4()
SOMEONE_ELSE = uuid.uuid4()
ADMIN, WORKER, ADVISOR = Role.ADMIN, Role.WORKER, Role.ADVISOR

MINE = TaskFacts(created_by=ME)
THEIRS = TaskFacts(created_by=SOMEONE_ELSE)
ORPHANED = TaskFacts(created_by=None)  # creator's account was deleted
LOCKED_MINE = TaskFacts(created_by=ME, harvest_year_locked=True)

Y = None  # allowed
# The PRD's Role matrix. Each row: action, task facts, then expected outcome for
# Admin, Worker, Advisor (None = allowed, otherwise the Denial).
MATRIX: list[tuple[Action, TaskFacts | None, Denial | None, Denial | None, Denial | None]] = [
    (Action.READ, None, Y, Y, Y),
    (Action.READ_FARM_NUMBER, None, Y, Denial.ROLE, Denial.ROLE),
    (Action.MANAGE_FARM, None, Y, Denial.ROLE, Denial.ROLE),
    (Action.MANAGE_MEMBERS, None, Y, Denial.ROLE, Denial.ROLE),
    (Action.LOCK_HARVEST_YEAR, None, Y, Denial.ROLE, Denial.ROLE),
    (Action.CREATE_TASK, None, Y, Y, Y),
    (Action.EDIT_TASK, THEIRS, Y, Y, Y),
    (Action.COMPLETE_TASK, THEIRS, Y, Y, Denial.ROLE),
    (Action.REOPEN_TASK, THEIRS, Y, Y, Denial.ROLE),
    (Action.DISCARD_TASK, THEIRS, Y, Y, Denial.ROLE),
    (Action.RESTORE_TASK, THEIRS, Y, Y, Denial.ROLE),
    (Action.COMPLETE_TASK, MINE, Y, Y, Denial.ROLE),
    (Action.DELETE_TASK, MINE, Y, Y, Y),
    (Action.DELETE_TASK, THEIRS, Y, Denial.NOT_CREATOR, Denial.NOT_CREATOR),
    (Action.DELETE_TASK, ORPHANED, Y, Denial.NOT_CREATOR, Denial.NOT_CREATOR),
    # A Locked Harvest Year freezes every write, for everyone.
    (Action.EDIT_TASK, LOCKED_MINE, Denial.LOCKED, Denial.LOCKED, Denial.LOCKED),
    (Action.COMPLETE_TASK, LOCKED_MINE, Denial.LOCKED, Denial.LOCKED, Denial.LOCKED),
    (Action.REOPEN_TASK, LOCKED_MINE, Denial.LOCKED, Denial.LOCKED, Denial.LOCKED),
    (Action.DISCARD_TASK, LOCKED_MINE, Denial.LOCKED, Denial.LOCKED, Denial.LOCKED),
    (Action.RESTORE_TASK, LOCKED_MINE, Denial.LOCKED, Denial.LOCKED, Denial.LOCKED),
    (Action.DELETE_TASK, LOCKED_MINE, Denial.LOCKED, Denial.LOCKED, Denial.LOCKED),
    (Action.READ, LOCKED_MINE, Y, Y, Y),
]


@pytest.mark.parametrize(
    ("action", "task", "role", "expected"),
    [
        pytest.param(action, task, role, expected, id=f"{action}-{role}-{i}")
        for i, (action, task, *outcomes) in enumerate(MATRIX)
        for role, expected in zip((ADMIN, WORKER, ADVISOR), outcomes, strict=True)
    ],
)
def test_role_matrix(
    action: Action, task: TaskFacts | None, role: Role, expected: Denial | None
) -> None:
    decision = decide(Actor(ME, role), action, task)

    assert decision.allowed is (expected is None)
    assert decision.denial == expected


def test_every_action_is_covered_by_the_matrix() -> None:
    assert {row[0] for row in MATRIX} == set(Action)


def test_only_admins_and_workers_can_be_assigned() -> None:
    assert can_be_assigned(ADMIN)
    assert can_be_assigned(WORKER)
    assert not can_be_assigned(ADVISOR)
