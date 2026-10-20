"""Routes of the built-in password AuthProvider, plus the signed-in user's own view."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import joinedload

from cropstar_api.auth.dependencies import (
    AppMailer,
    AppSettings,
    Auth,
    CurrentIdentity,
    PasswordAuth,
    clear_session_cookie,
    session_token,
    set_session_cookie,
)
from cropstar_api.auth.mailer import Email
from cropstar_api.auth.provider import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    EmailTakenError,
    Identity,
)
from cropstar_api.db import Db
from cropstar_api.models import Farm, Membership, Role

router = APIRouter(tags=["auth"])

NewPassword = Annotated[str, Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)]
AnyPassword = Annotated[str, Field(max_length=MAX_PASSWORD_LENGTH)]
FarmName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Locale = Literal["de", "en"]


# ── Schemas ─────────────────────────────────────────────────────────────────


class AuthConfig(BaseModel):
    registration_open: bool
    password_reset_by_email: bool


class RegisterRequest(BaseModel):
    email: EmailStr
    password: NewPassword
    farm_name: FarmName


class SignInRequest(BaseModel):
    email: Annotated[str, Field(max_length=320)]
    password: AnyPassword


class ChangePasswordRequest(BaseModel):
    current_password: AnyPassword
    new_password: NewPassword


class PasswordResetRequest(BaseModel):
    email: Annotated[str, Field(max_length=320)]
    locale: Locale = "de"


class PasswordResetCompletion(BaseModel):
    token: Annotated[str, Field(max_length=200)]
    password: NewPassword


class UserOut(BaseModel):
    id: uuid.UUID
    email: str


class FarmOut(BaseModel):
    id: uuid.UUID
    name: str


class MembershipOut(BaseModel):
    farm: FarmOut
    role: Role


class Me(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/auth/config", operation_id="getAuthConfig")
def read_auth_config(settings: AppSettings, mailer: AppMailer) -> AuthConfig:
    """What this instance offers before anyone is signed in."""
    return AuthConfig(
        registration_open=settings.registration_open,
        password_reset_by_email=mailer.available,
    )


@router.post("/auth/register", operation_id="register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest, response: Response, db: Db, auth: PasswordAuth, settings: AppSettings
) -> Me:
    """Create a User and their first Farm with them as its Admin, then sign them in."""
    if not settings.registration_open:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="registration_closed")
    try:
        identity = auth.register(db, body.email, body.password)
    except EmailTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="email_taken") from None
    farm = Farm(name=body.farm_name)
    db.add(farm)
    db.flush()
    db.add(Membership(farm_id=farm.id, user_id=identity.user_id, role=Role.ADMIN))
    set_session_cookie(response, auth.open_session(db, identity), settings)
    return _me(db, identity)


@router.post("/auth/sign-in", operation_id="signIn")
def sign_in(
    body: SignInRequest, response: Response, db: Db, auth: PasswordAuth, settings: AppSettings
) -> Me:
    identity = auth.authenticate(db, body.email, body.password)
    if identity is None:
        # The same answer for an unknown email and a wrong password.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    set_session_cookie(response, auth.open_session(db, identity), settings)
    return _me(db, identity)


@router.post(
    "/auth/sign-out",
    operation_id="signOut",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def sign_out(
    request: Request, response: Response, db: Db, auth: Auth, settings: AppSettings
) -> None:
    token = session_token(request)
    if token:
        auth.close_session(db, token)
    clear_session_cookie(response, settings)


@router.post(
    "/auth/password",
    operation_id="changePassword",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    identity: CurrentIdentity,
    db: Db,
    auth: PasswordAuth,
) -> None:
    """Change the password; every other session of this user is signed out."""
    current = session_token(request) or ""
    if not auth.change_password(db, identity, body.current_password, body.new_password, current):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="wrong_password")


@router.post(
    "/auth/password-reset/request",
    operation_id="requestPasswordReset",
    status_code=status.HTTP_202_ACCEPTED,
)
def request_password_reset(
    body: PasswordResetRequest,
    background: BackgroundTasks,
    db: Db,
    auth: PasswordAuth,
    mailer: AppMailer,
    settings: AppSettings,
) -> None:
    """Email a reset link if the address belongs to a User. The answer never tells which."""
    if not mailer.available:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="email_not_configured")
    created = auth.create_reset_token(db, body.email)
    if created is None:
        return
    identity, token = created
    # Sent after the response, so the response time does not reveal whether the user exists.
    background.add_task(
        mailer.send, _reset_email(identity, token, body.locale, settings.public_base_url)
    )


@router.post(
    "/auth/password-reset/complete",
    operation_id="completePasswordReset",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def complete_password_reset(body: PasswordResetCompletion, db: Db, auth: PasswordAuth) -> None:
    if not auth.complete_reset(db, body.token, body.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_or_expired_token")


@router.get("/me", operation_id="getMe")
def read_me(identity: CurrentIdentity, db: Db) -> Me:
    """The signed-in User and the Farms they are a member of."""
    return _me(db, identity)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _me(db: DbSession, identity: Identity) -> Me:
    memberships = db.scalars(
        select(Membership)
        .options(joinedload(Membership.farm))
        .join(Farm)
        .where(Membership.user_id == identity.user_id)
        .order_by(Farm.name, Farm.id)
    ).all()
    return Me(
        user=UserOut(id=identity.user_id, email=identity.email),
        memberships=[
            MembershipOut(farm=FarmOut(id=m.farm.id, name=m.farm.name), role=m.role)
            for m in memberships
        ],
    )


_RESET_EMAIL = {
    "de": (
        "Cropstar: Passwort zurücksetzen",
        "Hallo,\n\njemand (hoffentlich du) möchte das Passwort für {email} bei Cropstar "
        "zurücksetzen. Mit diesem Link legst du ein neues fest; er gilt eine Stunde:\n\n"
        "{link}\n\nWenn du das nicht warst, ignoriere diese Nachricht. Dein Passwort bleibt "
        "unverändert.\n",
    ),
    "en": (
        "Cropstar: reset your password",
        "Hello,\n\nsomeone (hopefully you) asked to reset the Cropstar password for {email}. "
        "This link lets you choose a new one and is valid for one hour:\n\n{link}\n\n"
        "If this wasn't you, ignore this message. Your password stays unchanged.\n",
    ),
}


def _reset_email(identity: Identity, token: str, locale: Locale, base_url: str) -> Email:
    prefix = "" if locale == "de" else f"/{locale}"
    link = f"{base_url}{prefix}/app/reset-password?token={token}"
    subject, body = _RESET_EMAIL[locale]
    return Email(
        to=identity.email, subject=subject, body=body.format(email=identity.email, link=link)
    )
