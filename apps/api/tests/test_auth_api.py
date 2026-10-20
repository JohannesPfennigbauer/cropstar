import re
from typing import Any

from fastapi.testclient import TestClient

from cropstar_api.app import create_app
from cropstar_api.settings import Settings
from tests.conftest import RecordingMailer

ANNA = {"email": "anna@example.at", "password": "correct horse", "farm_name": "Hof Gruber"}


def register(client: TestClient) -> Any:
    response = client.post("/api/auth/register", json=ANNA)
    assert response.status_code == 201, response.text
    return response.json()


def test_registering_creates_a_farm_with_the_user_as_admin_and_signs_in(
    client: TestClient,
) -> None:
    me = register(client)

    assert me["user"]["email"] == "anna@example.at"
    assert [(m["farm"]["name"], m["role"]) for m in me["memberships"]] == [("Hof Gruber", "admin")]
    assert client.get("/api/me").json() == me


def test_session_cookie_is_http_only_strict_and_persistent(client: TestClient) -> None:
    response = client.post("/api/auth/register", json=ANNA)

    cookie = response.headers["set-cookie"]
    assert cookie.startswith("cropstar_session=")
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Max-Age=2592000" in cookie
    assert "Path=/" in cookie


def test_session_cookie_is_secure_by_default() -> None:
    assert Settings().cookie_secure is True


def test_an_email_can_register_only_once(client: TestClient) -> None:
    register(client)

    response = client.post("/api/auth/register", json={**ANNA, "email": "ANNA@example.at"})

    assert response.status_code == 409
    assert response.json()["detail"] == "email_taken"


def test_registration_rejects_short_passwords_and_blank_farm_names(client: TestClient) -> None:
    assert client.post("/api/auth/register", json={**ANNA, "password": "short"}).status_code == 422
    assert client.post("/api/auth/register", json={**ANNA, "farm_name": "  "}).status_code == 422
    assert (
        client.post("/api/auth/register", json={**ANNA, "email": "not-an-email"}).status_code == 422
    )


def test_closed_registration_refuses_new_users(settings: Settings, mailer: RecordingMailer) -> None:
    closed = settings.model_copy(update={"registration_open": False})
    with TestClient(create_app(closed, mailer=mailer)) as client:
        assert client.get("/api/auth/config").json()["registration_open"] is False
        response = client.post("/api/auth/register", json=ANNA)

    assert response.status_code == 403
    assert response.json()["detail"] == "registration_closed"


def test_failed_sign_in_does_not_reveal_whether_the_email_exists(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    wrong_password = client.post(
        "/api/auth/sign-in", json={"email": ANNA["email"], "password": "wrong horse"}
    )
    unknown_email = client.post(
        "/api/auth/sign-in", json={"email": "nobody@example.at", "password": "wrong horse"}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {"detail": "invalid_credentials"}


def test_sign_in_and_sign_out(client: TestClient) -> None:
    register(client)
    client.cookies.clear()
    assert client.get("/api/me").status_code == 401

    signed_in = client.post(
        "/api/auth/sign-in", json={"email": "ANNA@example.at", "password": ANNA["password"]}
    )
    assert signed_in.status_code == 200
    token = client.cookies["cropstar_session"]
    assert client.get("/api/me").status_code == 200

    signed_out = client.post("/api/auth/sign-out")
    assert signed_out.status_code == 204
    assert client.get("/api/me").status_code == 401

    # The old cookie is dead on the server, not only removed from the browser.
    client.cookies.set("cropstar_session", token)
    assert client.get("/api/me").status_code == 401


def test_me_requires_a_session(client: TestClient) -> None:
    response = client.get("/api/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "not_signed_in"


def test_changing_the_password_requires_the_current_one(client: TestClient) -> None:
    register(client)

    wrong = client.post(
        "/api/auth/password",
        json={"current_password": "wrong horse", "new_password": "battery staple"},
    )
    right = client.post(
        "/api/auth/password",
        json={"current_password": ANNA["password"], "new_password": "battery staple"},
    )

    assert wrong.status_code == 403
    assert right.status_code == 204
    assert client.get("/api/me").status_code == 200
    client.cookies.clear()
    assert (
        client.post(
            "/api/auth/sign-in", json={"email": ANNA["email"], "password": "battery staple"}
        ).status_code
        == 200
    )


def test_password_reset_by_email(client: TestClient, mailer: RecordingMailer) -> None:
    register(client)
    old_session = client.cookies["cropstar_session"]
    assert client.get("/api/auth/config").json()["password_reset_by_email"] is True

    requested = client.post(
        "/api/auth/password-reset/request", json={"email": "Anna@example.at", "locale": "en"}
    )

    assert requested.status_code == 202
    [email] = mailer.sent
    assert email.to == "anna@example.at"
    link = re.search(r"https://cropstar\.test/en/app/reset-password\?token=(\S+)", email.body)
    assert link, email.body
    token = link.group(1)

    completed = client.post(
        "/api/auth/password-reset/complete", json={"token": token, "password": "battery staple"}
    )
    reused = client.post(
        "/api/auth/password-reset/complete", json={"token": token, "password": "another staple"}
    )

    assert completed.status_code == 204
    assert reused.status_code == 400
    assert reused.json()["detail"] == "invalid_or_expired_token"
    client.cookies.set("cropstar_session", old_session)
    assert client.get("/api/me").status_code == 401


def test_german_reset_link_has_no_locale_prefix(
    client: TestClient, mailer: RecordingMailer
) -> None:
    register(client)

    client.post("/api/auth/password-reset/request", json={"email": ANNA["email"]})

    assert "https://cropstar.test/app/reset-password?token=" in mailer.sent[0].body
    assert mailer.sent[0].subject == "Cropstar: Passwort zurücksetzen"


def test_password_reset_for_an_unknown_email_looks_the_same(
    client: TestClient, mailer: RecordingMailer
) -> None:
    response = client.post("/api/auth/password-reset/request", json={"email": "nobody@example.at"})

    assert response.status_code == 202
    assert mailer.sent == []


def test_without_email_password_reset_is_unavailable(client_without_email: TestClient) -> None:
    config = client_without_email.get("/api/auth/config").json()
    response = client_without_email.post(
        "/api/auth/password-reset/request", json={"email": ANNA["email"]}
    )

    assert config["password_reset_by_email"] is False
    assert response.status_code == 503
    assert response.json()["detail"] == "email_not_configured"
