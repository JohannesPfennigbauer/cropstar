import uuid
from datetime import UTC, datetime, timedelta

import pytest

from cropstar_api.memberships import (
    FarmMembers,
    InvitationState,
    LastAdminError,
    ensure_an_admin_remains,
    invitation_state,
    plan_account_deletion,
)
from cropstar_api.models import Invitation, Role

ANNA, BERT, CARLA = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
NOW = datetime(2027, 3, 15, 8, 0, tzinfo=UTC)


class TestAnAdminRemains:
    def test_the_only_admin_cannot_leave_or_step_down(self) -> None:
        roles = {ANNA: Role.ADMIN, BERT: Role.WORKER}

        for new_role in (None, Role.WORKER, Role.ADVISOR):
            with pytest.raises(LastAdminError):
                ensure_an_admin_remains(roles, ANNA, new_role)

    def test_one_of_two_admins_can(self) -> None:
        roles = {ANNA: Role.ADMIN, BERT: Role.ADMIN}

        ensure_an_admin_remains(roles, ANNA, None)
        ensure_an_admin_remains(roles, ANNA, Role.ADVISOR)

    def test_others_come_and_go_freely(self) -> None:
        roles = {ANNA: Role.ADMIN, BERT: Role.WORKER, CARLA: Role.ADVISOR}

        ensure_an_admin_remains(roles, BERT, None)
        ensure_an_admin_remains(roles, CARLA, Role.WORKER)
        ensure_an_admin_remains(roles, BERT, Role.ADMIN)

    def test_the_last_person_may_leave_an_otherwise_empty_farm(self) -> None:
        ensure_an_admin_remains({ANNA: Role.ADMIN}, ANNA, None)


def invitation(**overrides: object) -> Invitation:
    fields: dict[str, object] = {
        "expires_at": NOW + timedelta(days=7),
        "revoked_at": None,
        "accepted_at": None,
    }
    fields.update(overrides)
    return Invitation(**fields)


class TestInvitationState:
    def test_valid_until_it_expires(self) -> None:
        assert invitation_state(invitation(), NOW) is InvitationState.VALID
        expired = invitation(expires_at=NOW)
        assert invitation_state(expired, NOW) is InvitationState.EXPIRED

    def test_revoked(self) -> None:
        assert invitation_state(invitation(revoked_at=NOW), NOW) is InvitationState.REVOKED

    def test_used_wins_over_everything(self) -> None:
        used = invitation(accepted_at=NOW, revoked_at=NOW, expires_at=NOW - timedelta(days=1))
        assert invitation_state(used, NOW) is InvitationState.USED


class TestAccountDeletion:
    def test_farms_with_nobody_else_go_with_the_account(self) -> None:
        own = FarmMembers(uuid.uuid4(), "Hof Anna", {ANNA: Role.ADMIN})

        plan = plan_account_deletion(ANNA, [own])

        assert plan.farms_to_delete == [own.farm_id]
        assert plan.blocking_farms == []

    def test_the_last_admin_of_a_shared_farm_must_hand_over_first(self) -> None:
        shared = FarmMembers(uuid.uuid4(), "Hof Gruber", {ANNA: Role.ADMIN, BERT: Role.WORKER})
        co_admin = FarmMembers(uuid.uuid4(), "Hof Huber", {ANNA: Role.ADMIN, CARLA: Role.ADMIN})
        advising = FarmMembers(uuid.uuid4(), "Hof Maier", {ANNA: Role.ADVISOR, BERT: Role.ADMIN})

        plan = plan_account_deletion(ANNA, [shared, co_admin, advising])

        assert plan.blocking_farms == ["Hof Gruber"]
        assert plan.farms_to_delete == []
