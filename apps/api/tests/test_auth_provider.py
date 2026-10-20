from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from cropstar_api.auth.provider import EmailTakenError, PasswordAuthProvider


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2027, 3, 1, 8, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def provider(clock: Clock | None = None) -> PasswordAuthProvider:
    return PasswordAuthProvider(timedelta(days=30), timedelta(hours=1), clock or Clock())


def test_registered_user_signs_in_with_any_casing_of_their_email(db: Session) -> None:
    auth = provider()
    registered = auth.register(db, "  Anna@Example.AT ", "correct horse")

    assert registered.email == "anna@example.at"
    assert auth.authenticate(db, "ANNA@example.at", "correct horse") == registered


def test_wrong_password_and_unknown_email_both_fail(db: Session) -> None:
    auth = provider()
    auth.register(db, "anna@example.at", "correct horse")

    assert auth.authenticate(db, "anna@example.at", "wrong horse") is None
    assert auth.authenticate(db, "nobody@example.at", "correct horse") is None


def test_an_email_can_register_only_once(db: Session) -> None:
    auth = provider()
    auth.register(db, "anna@example.at", "correct horse")

    try:
        auth.register(db, "ANNA@example.at", "another horse")
    except EmailTakenError:
        return
    raise AssertionError("expected EmailTakenError")


def test_session_resolves_until_it_expires(db: Session) -> None:
    clock = Clock()
    auth = provider(clock)
    identity = auth.register(db, "anna@example.at", "correct horse")
    token = auth.open_session(db, identity)

    clock.now += timedelta(days=29, hours=23)
    assert auth.resolve_session(db, token) == identity

    clock.now += timedelta(hours=2)
    assert auth.resolve_session(db, token) is None


def test_closed_session_no_longer_resolves(db: Session) -> None:
    auth = provider()
    identity = auth.register(db, "anna@example.at", "correct horse")
    token = auth.open_session(db, identity)

    auth.close_session(db, token)

    assert auth.resolve_session(db, token) is None


def test_unknown_token_does_not_resolve(db: Session) -> None:
    assert provider().resolve_session(db, "not-a-token") is None


def test_changing_the_password_keeps_this_session_and_ends_the_others(db: Session) -> None:
    auth = provider()
    identity = auth.register(db, "anna@example.at", "correct horse")
    this_browser = auth.open_session(db, identity)
    other_browser = auth.open_session(db, identity)

    assert not auth.change_password(db, identity, "wrong", "battery staple", this_browser)
    assert auth.change_password(db, identity, "correct horse", "battery staple", this_browser)

    assert auth.resolve_session(db, this_browser) == identity
    assert auth.resolve_session(db, other_browser) is None
    assert auth.authenticate(db, "anna@example.at", "battery staple") == identity
    assert auth.authenticate(db, "anna@example.at", "correct horse") is None


def test_operator_password_reset_signs_the_user_out_everywhere(db: Session) -> None:
    auth = provider()
    identity = auth.register(db, "anna@example.at", "correct horse")
    token = auth.open_session(db, identity)

    assert auth.set_password(db, "Anna@example.at", "battery staple")

    assert auth.resolve_session(db, token) is None
    assert auth.authenticate(db, "anna@example.at", "battery staple") == identity
    assert not auth.set_password(db, "nobody@example.at", "battery staple")


def test_reset_token_works_once_and_signs_the_user_out(db: Session) -> None:
    auth = provider()
    identity = auth.register(db, "anna@example.at", "correct horse")
    session = auth.open_session(db, identity)
    created = auth.create_reset_token(db, "anna@example.at")
    assert created is not None
    _, token = created

    assert auth.complete_reset(db, token, "battery staple")
    assert not auth.complete_reset(db, token, "another staple")

    assert auth.resolve_session(db, session) is None
    assert auth.authenticate(db, "anna@example.at", "battery staple") == identity


def test_reset_token_expires_after_an_hour(db: Session) -> None:
    clock = Clock()
    auth = provider(clock)
    auth.register(db, "anna@example.at", "correct horse")
    created = auth.create_reset_token(db, "anna@example.at")
    assert created is not None

    clock.now += timedelta(hours=1, seconds=1)

    assert not auth.complete_reset(db, created[1], "battery staple")


def test_using_one_reset_link_invalidates_the_others(db: Session) -> None:
    auth = provider()
    auth.register(db, "anna@example.at", "correct horse")
    first = auth.create_reset_token(db, "anna@example.at")
    second = auth.create_reset_token(db, "anna@example.at")
    assert first is not None
    assert second is not None

    assert auth.complete_reset(db, second[1], "battery staple")

    assert not auth.complete_reset(db, first[1], "another staple")


def test_no_reset_token_for_an_unknown_email(db: Session) -> None:
    assert provider().create_reset_token(db, "nobody@example.at") is None
