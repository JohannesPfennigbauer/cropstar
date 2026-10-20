"""Farms, their members and invitations."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, status
from pydantic import BaseModel, EmailStr, StringConstraints
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session as DbSession

from cropstar_api.auth.dependencies import AppMailer, AppSettings, CurrentIdentity
from cropstar_api.auth.mailer import Email
from cropstar_api.auth.provider import hash_token
from cropstar_api.db import Db
from cropstar_api.farms import FarmMembership
from cropstar_api.invitations import find_invitation, redeem_invitation
from cropstar_api.memberships import (
    InvitationState,
    LastAdminError,
    ensure_an_admin_remains,
    invitation_state,
)
from cropstar_api.models import Farm, Invitation, Membership, Role, Task, User
from cropstar_api.policy import Action, Actor, can_be_assigned, decide
from cropstar_api.routes.auth import Me, me_of

router = APIRouter(tags=["farms"])

FarmName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
AmaFarmNumber = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{1,20}$")]
Locale = Literal["de", "en"]


# ── Schemas ─────────────────────────────────────────────────────────────────


class FarmCreate(BaseModel):
    name: FarmName


class FarmOut(BaseModel):
    id: uuid.UUID
    name: str
    # Only Admins see it; null for everyone else.
    ama_farm_number: str | None
    role: Role
    member_count: int


class FarmUpdate(BaseModel):
    name: FarmName | None = None
    ama_farm_number: AmaFarmNumber | None = None


class PersonOut(BaseModel):
    id: uuid.UUID
    email: str


class MemberOut(BaseModel):
    user: PersonOut
    role: Role
    assignable: bool
    joined_at: datetime


class RoleChange(BaseModel):
    role: Role


class InvitationCreate(BaseModel):
    role: Role
    valid_days: Literal[1, 7, 30] = 7
    # Optional: with email configured, the link is also sent here.
    email: EmailStr | None = None
    locale: Locale = "de"


class InvitationOut(BaseModel):
    id: uuid.UUID
    role: Role
    email: str | None
    created_at: datetime
    expires_at: datetime
    state: InvitationState


class InvitationCreated(BaseModel):
    invitation: InvitationOut
    # Shown once: only a hash of the token is stored.
    url: str
    emailed: bool


class InvitationPreview(BaseModel):
    farm_name: str
    role: Role
    invited_by: str | None
    expires_at: datetime
    state: InvitationState


# ── Farms ───────────────────────────────────────────────────────────────────


@router.post("/farms", operation_id="createFarm", status_code=status.HTTP_201_CREATED)
def create_farm(body: FarmCreate, identity: CurrentIdentity, db: Db) -> Me:
    """Another Farm, with the caller as its Admin."""
    farm = Farm(name=body.name)
    db.add(farm)
    db.flush()
    db.add(Membership(farm_id=farm.id, user_id=identity.user_id, role=Role.ADMIN))
    db.flush()
    return me_of(db, identity)


@router.get("/farms/{farm_id}", operation_id="getFarm")
def read_farm(membership: FarmMembership, db: Db) -> FarmOut:
    return _farm_out(db, membership)


@router.patch("/farms/{farm_id}", operation_id="updateFarm")
def update_farm(body: FarmUpdate, membership: FarmMembership, db: Db) -> FarmOut:
    _require(membership, Action.MANAGE_FARM)
    farm = db.get_one(Farm, membership.farm_id)
    if "name" in body.model_fields_set:
        if body.name is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="name_required")
        farm.name = body.name
    if "ama_farm_number" in body.model_fields_set:
        farm.ama_farm_number = body.ama_farm_number
    db.flush()
    return _farm_out(db, membership)


@router.delete(
    "/farms/{farm_id}",
    operation_id="deleteFarm",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_farm(
    membership: FarmMembership,
    db: Db,
    confirm: Annotated[str, Query(description="The Farm's exact name, as confirmation")],
) -> None:
    """Irreversibly removes the Farm with all its Fields, Plots, Tasks and members."""
    _require(membership, Action.MANAGE_FARM)
    farm = db.get_one(Farm, membership.farm_id)
    if confirm.strip() != farm.name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="confirmation_mismatch")
    db.delete(farm)
    db.flush()


# ── Members ─────────────────────────────────────────────────────────────────


@router.get("/farms/{farm_id}/members", operation_id="listMembers")
def list_members(membership: FarmMembership, db: Db) -> list[MemberOut]:
    rows = db.execute(
        select(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.farm_id == membership.farm_id)
        .order_by(User.email)
    ).all()
    return [
        MemberOut(
            user=PersonOut(id=user.id, email=user.email),
            role=member.role,
            assignable=can_be_assigned(member.role),
            joined_at=member.created_at,
        )
        for user, member in rows
    ]


@router.patch("/farms/{farm_id}/members/{user_id}", operation_id="changeMemberRole")
def change_member_role(
    user_id: uuid.UUID, body: RoleChange, membership: FarmMembership, db: Db
) -> MemberOut:
    _require(membership, Action.MANAGE_MEMBERS)
    target = _member(db, membership.farm_id, user_id)
    _keep_an_admin(db, membership.farm_id, user_id, body.role)
    target.role = body.role
    if not can_be_assigned(body.role):
        _unassign(db, membership.farm_id, user_id)
    db.flush()
    user = db.get_one(User, user_id)
    return MemberOut(
        user=PersonOut(id=user.id, email=user.email),
        role=target.role,
        assignable=can_be_assigned(target.role),
        joined_at=target.created_at,
    )


@router.delete(
    "/farms/{farm_id}/members/{user_id}",
    operation_id="removeMember",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def remove_member(user_id: uuid.UUID, membership: FarmMembership, db: Db) -> None:
    """Admins remove others; everyone may leave. The last member deletes the Farm instead."""
    if user_id != membership.user_id:
        _require(membership, Action.MANAGE_MEMBERS)
    target = _member(db, membership.farm_id, user_id)
    if _member_count(db, membership.farm_id) == 1:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="last_member")
    _keep_an_admin(db, membership.farm_id, user_id, None)
    _unassign(db, membership.farm_id, user_id)
    db.delete(target)
    db.flush()


# ── Invitations ─────────────────────────────────────────────────────────────


@router.post(
    "/farms/{farm_id}/invitations",
    operation_id="createInvitation",
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    body: InvitationCreate,
    membership: FarmMembership,
    identity: CurrentIdentity,
    db: Db,
    settings: AppSettings,
    mailer: AppMailer,
    background: BackgroundTasks,
) -> InvitationCreated:
    _require(membership, Action.MANAGE_MEMBERS)
    now = datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        id=uuid.uuid4(),
        farm_id=membership.farm_id,
        token_hash=hash_token(token),
        role=body.role,
        email=str(body.email).lower() if body.email else None,
        created_by_id=identity.user_id,
        created_at=now,
        expires_at=now + timedelta(days=body.valid_days),
    )
    db.add(invitation)
    db.flush()
    prefix = "" if body.locale == "de" else f"/{body.locale}"
    url = f"{settings.public_base_url}{prefix}/app/invite/{token}"
    emailed = bool(invitation.email and mailer.available)
    if emailed and invitation.email:
        farm = db.get_one(Farm, membership.farm_id)
        background.add_task(
            mailer.send,
            _invitation_email(invitation.email, farm.name, body.role, url, body.locale),
        )
    return InvitationCreated(invitation=_invitation_out(invitation, now), url=url, emailed=emailed)


@router.get("/farms/{farm_id}/invitations", operation_id="listInvitations")
def list_invitations(membership: FarmMembership, db: Db) -> list[InvitationOut]:
    """Invitations not yet accepted or revoked, expired ones included."""
    _require(membership, Action.MANAGE_MEMBERS)
    now = datetime.now(UTC)
    invitations = db.scalars(
        select(Invitation)
        .where(
            Invitation.farm_id == membership.farm_id,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
        .order_by(Invitation.created_at.desc())
    )
    return [_invitation_out(invitation, now) for invitation in invitations]


@router.delete(
    "/farms/{farm_id}/invitations/{invitation_id}",
    operation_id="revokeInvitation",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def revoke_invitation(invitation_id: uuid.UUID, membership: FarmMembership, db: Db) -> None:
    _require(membership, Action.MANAGE_MEMBERS)
    invitation = db.scalar(
        select(Invitation).where(
            Invitation.id == invitation_id, Invitation.farm_id == membership.farm_id
        )
    )
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="invitation_not_found")
    if invitation.accepted_at is None and invitation.revoked_at is None:
        invitation.revoked_at = datetime.now(UTC)
        db.flush()


@router.get("/invitations/{token}", operation_id="previewInvitation")
def preview_invitation(token: str, db: Db) -> InvitationPreview:
    """What an invitation link offers; readable without signing in."""
    invitation = find_invitation(db, token)
    farm = db.get_one(Farm, invitation.farm_id)
    inviter = db.get(User, invitation.created_by_id) if invitation.created_by_id else None
    return InvitationPreview(
        farm_name=farm.name,
        role=invitation.role,
        invited_by=inviter.email if inviter else None,
        expires_at=invitation.expires_at,
        state=invitation_state(invitation, datetime.now(UTC)),
    )


@router.post("/invitations/{token}/accept", operation_id="acceptInvitation")
def accept_invitation(token: str, identity: CurrentIdentity, db: Db) -> Me:
    invitation = find_invitation(db, token)
    if db.get(Membership, (invitation.farm_id, identity.user_id)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="already_member")
    redeem_invitation(db, invitation, identity.user_id)
    return me_of(db, identity)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _require(membership: Membership, action: Action) -> None:
    decision = decide(Actor(membership.user_id, membership.role), action)
    if not decision:
        assert decision.denial is not None
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=decision.denial.value)


def _farm_out(db: DbSession, membership: Membership) -> FarmOut:
    farm = db.get_one(Farm, membership.farm_id)
    sees_number = decide(Actor(membership.user_id, membership.role), Action.READ_FARM_NUMBER)
    return FarmOut(
        id=farm.id,
        name=farm.name,
        ama_farm_number=farm.ama_farm_number if sees_number else None,
        role=membership.role,
        member_count=_member_count(db, farm.id),
    )


def _member(db: DbSession, farm_id: uuid.UUID, user_id: uuid.UUID) -> Membership:
    member = db.get(Membership, (farm_id, user_id))
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="member_not_found")
    return member


def _member_count(db: DbSession, farm_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).where(Membership.farm_id == farm_id)) or 0


def _keep_an_admin(
    db: DbSession, farm_id: uuid.UUID, user_id: uuid.UUID, new_role: Role | None
) -> None:
    roles = dict(
        db.execute(
            select(Membership.user_id, Membership.role).where(Membership.farm_id == farm_id)
        ).all()
    )
    try:
        ensure_an_admin_remains(roles, user_id, new_role)
    except LastAdminError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=LastAdminError.code) from None


def _unassign(db: DbSession, farm_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Who can no longer complete work on this Farm is no longer responsible for any."""
    db.execute(
        update(Task)
        .where(Task.farm_id == farm_id, Task.assignee_id == user_id)
        .values(assignee_id=None)
    )


def _invitation_out(invitation: Invitation, now: datetime) -> InvitationOut:
    return InvitationOut(
        id=invitation.id,
        role=invitation.role,
        email=invitation.email,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
        state=invitation_state(invitation, now),
    )


_ROLE_NAMES = {
    "de": {Role.ADMIN: "Admin", Role.WORKER: "Mitarbeiter", Role.ADVISOR: "Berater"},
    "en": {Role.ADMIN: "admin", Role.WORKER: "worker", Role.ADVISOR: "advisor"},
}
_INVITATION_EMAIL = {
    "de": (
        "Einladung zu {farm} auf Cropstar",
        "Hallo,\n\ndu bist eingeladen, dem Betrieb {farm} auf Cropstar als {role} "
        "beizutreten. Mit diesem Link trittst du bei; er gilt nur für eine Person:\n\n"
        "{url}\n\nWenn du damit nichts anfangen kannst, ignoriere diese Nachricht.\n",
    ),
    "en": (
        "Invitation to {farm} on Cropstar",
        "Hello,\n\nyou are invited to join the farm {farm} on Cropstar as {role}. "
        "This link lets you join; it works for one person only:\n\n{url}\n\n"
        "If this means nothing to you, ignore this message.\n",
    ),
}


def _invitation_email(to: str, farm: str, role: Role, url: str, locale: Locale) -> Email:
    subject, body = _INVITATION_EMAIL[locale]
    return Email(
        to=to,
        subject=subject.format(farm=farm),
        body=body.format(farm=farm, role=_ROLE_NAMES[locale][role], url=url),
    )
