"""Membership rules that hold no matter how they are reached. Pure: callers load the facts."""

import enum
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from cropstar_api.models import Invitation, Role


class LastAdminError(Exception):
    """The change would leave a Farm that still has members without an Admin."""

    code = "last_admin"


def ensure_an_admin_remains(
    roles: Mapping[uuid.UUID, Role], user_id: uuid.UUID, new_role: Role | None
) -> None:
    """Check that changing `user_id` to `new_role` (None = leaving) keeps an Admin, as long
    as anyone is left on the Farm."""
    after = dict(roles)
    if new_role is None:
        after.pop(user_id, None)
    else:
        after[user_id] = new_role
    if after and Role.ADMIN not in after.values():
        raise LastAdminError


class InvitationState(enum.StrEnum):
    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    USED = "used"


def invitation_state(invitation: Invitation, now: datetime) -> InvitationState:
    if invitation.accepted_at is not None:
        return InvitationState.USED
    if invitation.revoked_at is not None:
        return InvitationState.REVOKED
    if invitation.expires_at <= now:
        return InvitationState.EXPIRED
    return InvitationState.VALID


@dataclass(frozen=True)
class FarmMembers:
    farm_id: uuid.UUID
    farm_name: str
    roles: Mapping[uuid.UUID, Role]


@dataclass(frozen=True)
class AccountDeletionPlan:
    # Farms the person is the only member of; they go with the account.
    farms_to_delete: list[uuid.UUID]
    # Farms that would be left without an Admin; the Admin Role must be handed over first.
    blocking_farms: list[str]


def plan_account_deletion(user_id: uuid.UUID, farms: list[FarmMembers]) -> AccountDeletionPlan:
    to_delete: list[uuid.UUID] = []
    blocking: list[str] = []
    for farm in farms:
        if set(farm.roles) == {user_id}:
            to_delete.append(farm.farm_id)
            continue
        try:
            ensure_an_admin_remains(farm.roles, user_id, None)
        except LastAdminError:
            blocking.append(farm.farm_name)
    return AccountDeletionPlan(to_delete, sorted(blocking))
