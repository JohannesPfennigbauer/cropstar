from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status

from cropstar_api.auth.mailer import Mailer
from cropstar_api.auth.provider import AuthProvider, Identity, PasswordAuthProvider
from cropstar_api.db import Db
from cropstar_api.settings import Settings

SESSION_COOKIE = "cropstar_session"


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_auth(request: Request) -> AuthProvider:
    provider: AuthProvider = request.app.state.auth
    return provider


def get_password_auth(request: Request) -> PasswordAuthProvider:
    provider: PasswordAuthProvider = request.app.state.auth
    return provider


def get_mailer(request: Request) -> Mailer:
    mailer: Mailer = request.app.state.mailer
    return mailer


AppSettings = Annotated[Settings, Depends(get_settings)]
Auth = Annotated[AuthProvider, Depends(get_auth)]
PasswordAuth = Annotated[PasswordAuthProvider, Depends(get_password_auth)]
AppMailer = Annotated[Mailer, Depends(get_mailer)]


def session_token(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def current_identity(request: Request, db: Db, auth: Auth) -> Identity:
    token = session_token(request)
    identity = auth.resolve_session(db, token) if token else None
    if identity is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="not_signed_in")
    return identity


CurrentIdentity = Annotated[Identity, Depends(current_identity)]


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_lifetime_days * 24 * 60 * 60,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="strict"
    )
