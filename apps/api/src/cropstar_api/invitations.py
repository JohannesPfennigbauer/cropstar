"""Finding and redeeming invitation links; shared by joining and registering."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cropstar_api.auth.provider import hash_token
from cropstar_api.memberships import InvitationState, invitation_state
from cropstar_api.models import Invitation, Membership


def find_invitation(db: DbSession, token: str) -> Invitation:
    invitation = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="invitation_not_found")
    return invitation


def redeem_invitation(db: DbSession, invitation: Invitation, user_id: uuid.UUID) -> None:
    """Turn a valid invitation into a Membership; any other state is 410 Gone."""
    now = datetime.now(UTC)
    state = invitation_state(invitation, now)
    if state is not InvitationState.VALID:
        raise HTTPException(status.HTTP_410_GONE, detail=f"invitation_{state.value}")
    db.add(Membership(farm_id=invitation.farm_id, user_id=user_id, role=invitation.role))
    invitation.accepted_by_id = user_id
    invitation.accepted_at = now
    db.flush()
