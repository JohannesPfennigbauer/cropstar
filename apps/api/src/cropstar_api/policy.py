"""Access Policy: who may do what on a Farm. The only place permissions live.

Pure and without I/O: callers gather the facts (the actor's Role, whether a Task's Harvest
Year is locked, who created it) and ask `decide`.
"""

import enum
import uuid
from dataclasses import dataclass

from cropstar_api.models import Role


class Action(enum.StrEnum):
    READ = "read"
    READ_FARM_NUMBER = "read_farm_number"
    MANAGE_FARM = "manage_farm"
    MANAGE_MEMBERS = "manage_members"
    LOCK_HARVEST_YEAR = "lock_harvest_year"
    CREATE_TASK = "create_task"
    EDIT_TASK = "edit_task"
    COMPLETE_TASK = "complete_task"
    REOPEN_TASK = "reopen_task"
    DISCARD_TASK = "discard_task"
    RESTORE_TASK = "restore_task"
    DELETE_TASK = "delete_task"


class Denial(enum.StrEnum):
    ROLE = "forbidden_for_role"
    NOT_CREATOR = "only_admin_or_creator"
    LOCKED = "harvest_year_locked"


@dataclass(frozen=True)
class Actor:
    user_id: uuid.UUID
    role: Role


@dataclass(frozen=True)
class TaskFacts:
    created_by: uuid.UUID | None
    harvest_year_locked: bool = False


@dataclass(frozen=True)
class Decision:
    allowed: bool
    denial: Denial | None = None

    def __bool__(self) -> bool:
        return self.allowed


ALLOW = Decision(True)

_ADMIN_ONLY = frozenset(
    {Action.READ_FARM_NUMBER, Action.MANAGE_FARM, Action.MANAGE_MEMBERS, Action.LOCK_HARVEST_YEAR}
)
# Confirming that work happened is for people who work on the Farm, not Advisors.
_STATUS_CHANGES = frozenset(
    {Action.COMPLETE_TASK, Action.REOPEN_TASK, Action.DISCARD_TASK, Action.RESTORE_TASK}
)
_TASK_WRITES = _STATUS_CHANGES | {Action.CREATE_TASK, Action.EDIT_TASK, Action.DELETE_TASK}

TASK_ACTIONS = (
    Action.EDIT_TASK,
    Action.COMPLETE_TASK,
    Action.REOPEN_TASK,
    Action.DISCARD_TASK,
    Action.RESTORE_TASK,
    Action.DELETE_TASK,
)


def decide(actor: Actor, action: Action, task: TaskFacts | None = None) -> Decision:
    if action in _TASK_WRITES and task is not None and task.harvest_year_locked:
        return Decision(False, Denial.LOCKED)
    if action in _ADMIN_ONLY:
        return ALLOW if actor.role is Role.ADMIN else Decision(False, Denial.ROLE)
    if action in _STATUS_CHANGES:
        return Decision(False, Denial.ROLE) if actor.role is Role.ADVISOR else ALLOW
    if action is Action.DELETE_TASK:
        if actor.role is Role.ADMIN:
            return ALLOW
        is_creator = task is not None and task.created_by == actor.user_id
        return ALLOW if is_creator else Decision(False, Denial.NOT_CREATOR)
    # READ, CREATE_TASK, EDIT_TASK: every member.
    return ALLOW


def can_be_assigned(role: Role) -> bool:
    """Only people who can complete work can be responsible for it."""
    return role is not Role.ADVISOR
