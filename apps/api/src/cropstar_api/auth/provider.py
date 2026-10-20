import hashlib
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from cropstar_api.models import PasswordCredential, PasswordResetToken, Session, User

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 256


@dataclass(frozen=True)
class Identity:
    """The internal identity of a signed-in User; all the rest of the API ever sees."""

    user_id: uuid.UUID
    email: str


class AuthProvider(Protocol):
    """What the app needs from any way of signing in (built-in passwords today, OIDC later)."""

    def resolve_session(self, db: DbSession, token: str) -> Identity | None: ...

    def close_session(self, db: DbSession, token: str) -> None: ...


class EmailTakenError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PasswordAuthProvider:
    """The built-in AuthProvider: email + password, argon2 hashes, sessions in Postgres."""

    def __init__(
        self,
        session_lifetime: timedelta,
        reset_token_lifetime: timedelta = timedelta(hours=1),
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.session_lifetime = session_lifetime
        self._reset_token_lifetime = reset_token_lifetime
        self._clock = clock
        self._hasher = PasswordHasher()
        # Verified against when the email is unknown, so both paths take the same time.
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(16))

    # ── Accounts ────────────────────────────────────────────────────────────

    def register(self, db: DbSession, email: str, password: str) -> Identity:
        email = normalize_email(email)
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            raise EmailTakenError(email)
        user = User(email=email)
        try:
            # A savepoint, so losing a race against a concurrent registration leaves the
            # surrounding transaction usable.
            with db.begin_nested():
                db.add(user)
        except IntegrityError:
            raise EmailTakenError(email) from None
        db.add(PasswordCredential(user_id=user.id, password_hash=self._hasher.hash(password)))
        db.flush()
        return Identity(user.id, user.email)

    def authenticate(self, db: DbSession, email: str, password: str) -> Identity | None:
        row = db.execute(
            select(User, PasswordCredential)
            .join(PasswordCredential, PasswordCredential.user_id == User.id)
            .where(User.email == normalize_email(email))
        ).one_or_none()
        if row is None:
            self._verify(self._dummy_hash, password)
            return None
        user, credential = row
        if not self._verify(credential.password_hash, password):
            return None
        if self._hasher.check_needs_rehash(credential.password_hash):
            credential.password_hash = self._hasher.hash(password)
        return Identity(user.id, user.email)

    def change_password(
        self, db: DbSession, identity: Identity, current: str, new: str, keep_session: str
    ) -> bool:
        credential = db.get(PasswordCredential, identity.user_id)
        if credential is None or not self._verify(credential.password_hash, current):
            return False
        self._store_password(credential, new)
        self.close_all_sessions(db, identity.user_id, except_token=keep_session)
        return True

    def set_password(self, db: DbSession, email: str, new: str) -> bool:
        """Set a password without the current one (Instance Operator); signs the user out."""
        user = db.scalar(select(User).where(User.email == normalize_email(email)))
        if user is None:
            return False
        credential = db.get(PasswordCredential, user.id)
        if credential is None:
            db.add(PasswordCredential(user_id=user.id, password_hash=self._hasher.hash(new)))
        else:
            self._store_password(credential, new)
        self.close_all_sessions(db, user.id)
        return True

    # ── Sessions ────────────────────────────────────────────────────────────

    def open_session(self, db: DbSession, identity: Identity) -> str:
        now = self._clock()
        db.execute(
            delete(Session).where(Session.user_id == identity.user_id, Session.expires_at <= now)
        )
        token = secrets.token_urlsafe(32)
        db.add(
            Session(
                token_hash=_hash_token(token),
                user_id=identity.user_id,
                expires_at=now + self.session_lifetime,
            )
        )
        db.flush()
        return token

    def resolve_session(self, db: DbSession, token: str) -> Identity | None:
        row = db.execute(
            select(User.id, User.email)
            .join(Session, Session.user_id == User.id)
            .where(Session.token_hash == _hash_token(token), Session.expires_at > self._clock())
        ).one_or_none()
        return Identity(row.id, row.email) if row else None

    def close_session(self, db: DbSession, token: str) -> None:
        db.execute(delete(Session).where(Session.token_hash == _hash_token(token)))

    def close_all_sessions(
        self, db: DbSession, user_id: uuid.UUID, except_token: str | None = None
    ) -> None:
        statement = delete(Session).where(Session.user_id == user_id)
        if except_token is not None:
            statement = statement.where(Session.token_hash != _hash_token(except_token))
        db.execute(statement)

    # ── Password reset ──────────────────────────────────────────────────────

    def create_reset_token(self, db: DbSession, email: str) -> tuple[Identity, str] | None:
        user = db.scalar(select(User).where(User.email == normalize_email(email)))
        if user is None:
            return None
        token = secrets.token_urlsafe(32)
        db.add(
            PasswordResetToken(
                token_hash=_hash_token(token),
                user_id=user.id,
                expires_at=self._clock() + self._reset_token_lifetime,
            )
        )
        db.flush()
        return Identity(user.id, user.email), token

    def complete_reset(self, db: DbSession, token: str, new: str) -> bool:
        now = self._clock()
        reset = db.scalar(
            select(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == _hash_token(token),
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
            .with_for_update()
        )
        if reset is None:
            return False
        reset.used_at = now
        # Any other outstanding links for this user stop working too.
        db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == reset.user_id, PasswordResetToken.used_at.is_(None)
            )
            .values(used_at=now)
        )
        credential = db.get(PasswordCredential, reset.user_id)
        if credential is None:
            db.add(PasswordCredential(user_id=reset.user_id, password_hash=self._hasher.hash(new)))
        else:
            self._store_password(credential, new)
        self.close_all_sessions(db, reset.user_id)
        return True

    # ── Internals ───────────────────────────────────────────────────────────

    def _store_password(self, credential: PasswordCredential, new: str) -> None:
        credential.password_hash = self._hasher.hash(new)
        credential.updated_at = self._clock()

    def _verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False
