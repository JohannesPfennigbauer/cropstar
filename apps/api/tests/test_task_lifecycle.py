import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from cropstar_api.models import Priority, Role, Task, TaskStatus
from cropstar_api.policy import Action, Actor
from cropstar_api.tasks.lifecycle import (
    ForbiddenError,
    InvalidAssigneeError,
    InvalidTransitionError,
    NewTask,
    TaskLifecycle,
    TaskNotFoundError,
)

FARM = uuid.uuid4()
OTHER_FARM = uuid.uuid4()


class InMemoryTasks:
    def __init__(self) -> None:
        self.tasks: dict[uuid.UUID, Task] = {}
        self.roles: dict[tuple[uuid.UUID, uuid.UUID], Role] = {}

    def get(self, farm_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
        task = self.tasks.get(task_id)
        return task if task is not None and task.farm_id == farm_id else None

    def add(self, task: Task) -> None:
        self.tasks[task.id] = task

    def delete(self, task: Task) -> None:
        del self.tasks[task.id]

    def role_of(self, farm_id: uuid.UUID, user_id: uuid.UUID) -> Role | None:
        return self.roles.get((farm_id, user_id))


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2027, 3, 15, 7, 30, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def repo() -> InMemoryTasks:
    return InMemoryTasks()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def lifecycle(repo: InMemoryTasks, clock: Clock) -> TaskLifecycle:
    return TaskLifecycle(repo, clock)


def member(repo: InMemoryTasks, role: Role, farm: uuid.UUID = FARM) -> Actor:
    actor = Actor(uuid.uuid4(), role)
    repo.roles[(farm, actor.user_id)] = role
    return actor


def test_a_new_task_is_open_and_remembers_who_created_it(
    lifecycle: TaskLifecycle, repo: InMemoryTasks, clock: Clock
) -> None:
    anna = member(repo, Role.WORKER)

    task = lifecycle.create(
        anna, FARM, NewTask("Zaun reparieren", due_date=date(2027, 3, 20), priority=Priority.HIGH)
    )

    assert repo.tasks[task.id] is task
    assert task.status is TaskStatus.OPEN
    assert (task.created_by_id, task.created_at) == (anna.user_id, clock.now)
    assert (task.completed_by_id, task.completed_at) == (None, None)
    assert task.priority is Priority.HIGH


def test_recording_after_the_fact_creates_a_done_task(
    lifecycle: TaskLifecycle, repo: InMemoryTasks, clock: Clock
) -> None:
    anna = member(repo, Role.WORKER)

    task = lifecycle.create(anna, FARM, NewTask("Traktor-Service", done=True))

    assert task.status is TaskStatus.DONE
    assert (task.completed_by_id, task.completed_at) == (anna.user_id, clock.now)


def test_advisors_create_tasks_but_cannot_record_them_as_done(
    lifecycle: TaskLifecycle, repo: InMemoryTasks
) -> None:
    berta = member(repo, Role.ADVISOR)

    assert lifecycle.create(berta, FARM, NewTask("Bodenprobe ziehen")).status is TaskStatus.OPEN
    with pytest.raises(ForbiddenError) as denied:
        lifecycle.create(berta, FARM, NewTask("Schon gemacht", done=True))
    assert denied.value.code == "forbidden_for_role"


def test_complete_reopen_complete(
    lifecycle: TaskLifecycle, repo: InMemoryTasks, clock: Clock
) -> None:
    anna = member(repo, Role.WORKER)
    task = lifecycle.create(anna, FARM, NewTask("Striegeln"))

    clock.now += timedelta(hours=2)
    lifecycle.complete(anna, FARM, task.id)
    assert (task.status, task.completed_at) == (TaskStatus.DONE, clock.now)

    lifecycle.reopen(anna, FARM, task.id)
    assert (task.status, task.completed_by_id, task.completed_at) == (TaskStatus.OPEN, None, None)

    lifecycle.complete(anna, FARM, task.id)
    assert task.status is TaskStatus.DONE


def test_discard_and_restore(lifecycle: TaskLifecycle, repo: InMemoryTasks) -> None:
    anna = member(repo, Role.ADMIN)
    task = lifecycle.create(anna, FARM, NewTask("Hecke schneiden"))

    assert lifecycle.discard(anna, FARM, task.id).status is TaskStatus.DISCARDED
    assert lifecycle.restore(anna, FARM, task.id).status is TaskStatus.OPEN


@pytest.mark.parametrize(
    ("start", "command"),
    [
        (TaskStatus.DONE, "complete"),
        (TaskStatus.DISCARDED, "complete"),
        (TaskStatus.OPEN, "reopen"),
        (TaskStatus.DISCARDED, "reopen"),
        (TaskStatus.DONE, "discard"),
        (TaskStatus.DISCARDED, "discard"),
        (TaskStatus.OPEN, "restore"),
        (TaskStatus.DONE, "restore"),
    ],
)
def test_transitions_only_from_their_status(
    lifecycle: TaskLifecycle, repo: InMemoryTasks, start: TaskStatus, command: str
) -> None:
    anna = member(repo, Role.ADMIN)
    task = lifecycle.create(anna, FARM, NewTask("Aufgabe"))
    task.status = start

    with pytest.raises(InvalidTransitionError):
        getattr(lifecycle, command)(anna, FARM, task.id)
    assert task.status is start


def test_advisors_cannot_change_status(lifecycle: TaskLifecycle, repo: InMemoryTasks) -> None:
    anna = member(repo, Role.WORKER)
    berta = member(repo, Role.ADVISOR)
    task = lifecycle.create(anna, FARM, NewTask("Düngen"))

    for command in ("complete", "discard"):
        with pytest.raises(ForbiddenError):
            getattr(lifecycle, command)(berta, FARM, task.id)
    assert task.status is TaskStatus.OPEN


def test_editing_changes_only_the_given_fields(
    lifecycle: TaskLifecycle, repo: InMemoryTasks, clock: Clock
) -> None:
    berta = member(repo, Role.ADVISOR)
    task = lifecycle.create(
        berta, FARM, NewTask("Bodenprobe", description="Schlag 3", priority=Priority.LOW)
    )

    clock.now += timedelta(days=1)
    lifecycle.edit(berta, FARM, task.id, {"title": "Bodenprobe ziehen", "description": None})

    assert (task.title, task.description, task.priority) == (
        "Bodenprobe ziehen",
        None,
        Priority.LOW,
    )
    assert task.updated_at == clock.now
    with pytest.raises(ValueError, match="status"):
        lifecycle.edit(berta, FARM, task.id, {"status": TaskStatus.DONE})


def test_only_admins_and_workers_of_this_farm_can_be_assigned(
    lifecycle: TaskLifecycle, repo: InMemoryTasks
) -> None:
    admin = member(repo, Role.ADMIN)
    worker = member(repo, Role.WORKER)
    advisor = member(repo, Role.ADVISOR)
    stranger = member(repo, Role.WORKER, farm=OTHER_FARM)

    task = lifecycle.create(admin, FARM, NewTask("Säen", assignee_id=worker.user_id))
    lifecycle.edit(admin, FARM, task.id, {"assignee_id": admin.user_id})
    lifecycle.edit(admin, FARM, task.id, {"assignee_id": None})

    for nobody in (advisor.user_id, stranger.user_id, uuid.uuid4()):
        with pytest.raises(InvalidAssigneeError):
            lifecycle.create(admin, FARM, NewTask("Säen", assignee_id=nobody))
        with pytest.raises(InvalidAssigneeError):
            lifecycle.edit(admin, FARM, task.id, {"assignee_id": nobody})
    assert task.assignee_id is None


def test_delete_is_for_admins_and_the_creator(
    lifecycle: TaskLifecycle, repo: InMemoryTasks
) -> None:
    admin = member(repo, Role.ADMIN)
    creator = member(repo, Role.WORKER)
    colleague = member(repo, Role.WORKER)
    mine = lifecycle.create(creator, FARM, NewTask("Meine"))
    theirs = lifecycle.create(creator, FARM, NewTask("Fremde"))

    with pytest.raises(ForbiddenError) as denied:
        lifecycle.delete(colleague, FARM, theirs.id)
    assert denied.value.code == "only_admin_or_creator"

    lifecycle.delete(creator, FARM, mine.id)
    lifecycle.delete(admin, FARM, theirs.id)
    assert repo.tasks == {}


def test_tasks_of_another_farm_are_not_found(lifecycle: TaskLifecycle, repo: InMemoryTasks) -> None:
    anna = member(repo, Role.ADMIN)
    task = lifecycle.create(anna, FARM, NewTask("Hier"))

    with pytest.raises(TaskNotFoundError):
        lifecycle.complete(anna, OTHER_FARM, task.id)


def test_allowed_actions_follow_role_and_status(
    lifecycle: TaskLifecycle, repo: InMemoryTasks
) -> None:
    worker = member(repo, Role.WORKER)
    advisor = member(repo, Role.ADVISOR)
    task = lifecycle.create(worker, FARM, NewTask("Ernte"))

    assert lifecycle.allowed_actions(worker, task) == [
        Action.EDIT_TASK,
        Action.COMPLETE_TASK,
        Action.DISCARD_TASK,
        Action.DELETE_TASK,
    ]
    assert lifecycle.allowed_actions(advisor, task) == [Action.EDIT_TASK]

    lifecycle.complete(worker, FARM, task.id)
    assert lifecycle.allowed_actions(worker, task) == [
        Action.EDIT_TASK,
        Action.REOPEN_TASK,
        Action.DELETE_TASK,
    ]
