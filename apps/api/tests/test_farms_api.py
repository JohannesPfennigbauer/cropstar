import re
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from cropstar_api.app import create_app
from cropstar_api.models import Farm, Invitation
from cropstar_api.settings import Settings
from tests.conftest import RecordingMailer

PASSWORD = "correct horse"
Client = Callable[..., TestClient]


@pytest.fixture
def new_client(settings: Settings, mailer: RecordingMailer) -> Iterator[Client]:
    clients: list[TestClient] = []

    def make(**overrides: Any) -> TestClient:
        client = TestClient(create_app(settings.model_copy(update=overrides), mailer=mailer))
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()


def register(client: TestClient, email: str, **body: Any) -> Any:
    response = client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD, **body}
    )
    assert response.status_code == 201, response.text
    return response.json()


def farm_of(me: Any, index: int = 0) -> str:
    farm_id: str = me["memberships"][index]["farm"]["id"]
    return farm_id


def invite(client: TestClient, farm_id: str, role: str = "worker", **body: Any) -> Any:
    response = client.post(f"/api/farms/{farm_id}/invitations", json={"role": role, **body})
    assert response.status_code == 201, response.text
    return response.json()


def token_of(created: Any) -> str:
    match = re.search(r"/app/invite/([^/?#]+)$", created["url"])
    assert match, created["url"]
    return match.group(1)


@pytest.fixture
def anna(new_client: Client) -> tuple[TestClient, str]:
    client = new_client()
    return client, farm_of(register(client, "anna@example.at", farm_name="Hof Gruber"))


def join(new_client: Client, admin: TestClient, farm_id: str, email: str, role: str) -> TestClient:
    token = token_of(invite(admin, farm_id, role))
    client = new_client()
    register(client, email, invitation_token=token)
    return client


# ── Farms ───────────────────────────────────────────────────────────────────


def test_a_user_can_run_several_farms(anna: tuple[TestClient, str]) -> None:
    client, _ = anna

    response = client.post("/api/farms", json={"name": "Hof Zwei"})

    assert response.status_code == 201
    assert sorted((m["farm"]["name"], m["role"]) for m in response.json()["memberships"]) == [
        ("Hof Gruber", "admin"),
        ("Hof Zwei", "admin"),
    ]


def test_registering_needs_a_farm_name_unless_invited(new_client: Client) -> None:
    response = new_client().post(
        "/api/auth/register", json={"email": "x@example.at", "password": PASSWORD}
    )

    assert (response.status_code, response.json()["detail"]) == (422, "farm_name_required")


def test_only_admins_see_and_change_the_farm(
    anna: tuple[TestClient, str], new_client: Client
) -> None:
    admin, farm_id = anna
    worker = join(new_client, admin, farm_id, "wolf@example.at", "worker")

    updated = admin.patch(
        f"/api/farms/{farm_id}", json={"name": "Hof Gruber-Maier", "ama_farm_number": "1234567"}
    )
    assert updated.status_code == 200
    assert (updated.json()["name"], updated.json()["ama_farm_number"]) == (
        "Hof Gruber-Maier",
        "1234567",
    )

    seen_by_worker = worker.get(f"/api/farms/{farm_id}").json()
    assert (seen_by_worker["name"], seen_by_worker["ama_farm_number"]) == ("Hof Gruber-Maier", None)
    assert (seen_by_worker["role"], seen_by_worker["member_count"]) == ("worker", 2)
    assert worker.patch(f"/api/farms/{farm_id}", json={"name": "Meins"}).status_code == 403
    assert admin.patch(f"/api/farms/{farm_id}", json={"ama_farm_number": "12a"}).status_code == 422


def test_deleting_a_farm_needs_its_name_and_removes_everything(
    anna: tuple[TestClient, str], new_client: Client, db: Session
) -> None:
    admin, farm_id = anna
    worker = join(new_client, admin, farm_id, "wolf@example.at", "worker")
    admin.post(f"/api/farms/{farm_id}/tasks", json={"title": "Zaun"})

    assert (
        worker.delete(f"/api/farms/{farm_id}", params={"confirm": "Hof Gruber"}).status_code == 403
    )
    wrong = admin.delete(f"/api/farms/{farm_id}", params={"confirm": "Hof"})
    assert (wrong.status_code, wrong.json()["detail"]) == (422, "confirmation_mismatch")

    assert (
        admin.delete(f"/api/farms/{farm_id}", params={"confirm": "Hof Gruber"}).status_code == 204
    )

    assert worker.get(f"/api/farms/{farm_id}/tasks").status_code == 404
    assert worker.get("/api/me").json()["memberships"] == []
    assert db.scalar(select(Farm).where(Farm.name == "Hof Gruber")) is None


# ── Invitations ─────────────────────────────────────────────────────────────


def test_invited_people_register_even_when_registration_is_closed(
    anna: tuple[TestClient, str], new_client: Client
) -> None:
    admin, farm_id = anna
    created = invite(admin, farm_id, "advisor")
    token = token_of(created)
    assert created["url"].startswith("https://cropstar.test/app/invite/")
    assert created["invitation"]["state"] == "valid"

    closed = new_client(registration_open=False)
    preview = closed.get(f"/api/invitations/{token}").json()
    assert (preview["farm_name"], preview["role"], preview["invited_by"], preview["state"]) == (
        "Hof Gruber",
        "advisor",
        "anna@example.at",
        "valid",
    )

    me = register(closed, "berta@example.at", invitation_token=token)

    assert [(m["farm"]["name"], m["role"]) for m in me["memberships"]] == [
        ("Hof Gruber", "advisor")
    ]
    assert closed.get(f"/api/invitations/{token}").json()["state"] == "used"
    assert admin.get(f"/api/farms/{farm_id}/invitations").json() == []
    again = new_client().post(
        "/api/auth/register",
        json={"email": "carla@example.at", "password": PASSWORD, "invitation_token": token},
    )
    assert (again.status_code, again.json()["detail"]) == (410, "invitation_used")


def test_existing_users_accept_an_invitation(
    anna: tuple[TestClient, str], new_client: Client
) -> None:
    admin, farm_id = anna
    stefan = new_client()
    register(stefan, "stefan@example.at", farm_name="Hof Huber")

    me = stefan.post(f"/api/invitations/{token_of(invite(admin, farm_id))}/accept").json()

    assert sorted((m["farm"]["name"], m["role"]) for m in me["memberships"]) == [
        ("Hof Gruber", "worker"),
        ("Hof Huber", "admin"),
    ]
    twice = stefan.post(f"/api/invitations/{token_of(invite(admin, farm_id))}/accept")
    assert (twice.status_code, twice.json()["detail"]) == (409, "already_member")


def test_revoked_and_expired_invitations_are_gone(
    anna: tuple[TestClient, str], new_client: Client, db: Session
) -> None:
    admin, farm_id = anna
    revoked = invite(admin, farm_id)
    expired = invite(admin, farm_id)
    assert (
        admin.delete(f"/api/farms/{farm_id}/invitations/{revoked['invitation']['id']}").status_code
        == 204
    )
    db.execute(
        update(Invitation)
        .where(Invitation.id == expired["invitation"]["id"])
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    db.commit()

    stefan = new_client()
    register(stefan, "stefan@example.at", farm_name="Hof Huber")
    for created, state in ((revoked, "revoked"), (expired, "expired")):
        token = token_of(created)
        assert stefan.get(f"/api/invitations/{token}").json()["state"] == state
        response = stefan.post(f"/api/invitations/{token}/accept")
        assert (response.status_code, response.json()["detail"]) == (410, f"invitation_{state}")
    pending = admin.get(f"/api/farms/{farm_id}/invitations").json()
    assert [(i["id"], i["state"]) for i in pending] == [(expired["invitation"]["id"], "expired")]
    assert new_client().get("/api/invitations/not-a-token").status_code == 404


def test_only_admins_manage_invitations(anna: tuple[TestClient, str], new_client: Client) -> None:
    admin, farm_id = anna
    worker = join(new_client, admin, farm_id, "wolf@example.at", "worker")

    assert (
        worker.post(f"/api/farms/{farm_id}/invitations", json={"role": "worker"}).status_code == 403
    )
    assert worker.get(f"/api/farms/{farm_id}/invitations").status_code == 403


def test_invitations_are_emailed_when_email_is_configured(
    anna: tuple[TestClient, str], mailer: RecordingMailer
) -> None:
    admin, farm_id = anna

    created = invite(admin, farm_id, email="Wolf@Example.at", locale="en")

    assert created["emailed"] is True
    assert created["url"].startswith("https://cropstar.test/en/app/invite/")
    [email] = mailer.sent
    assert email.to == "wolf@example.at"
    assert created["url"] in email.body
    assert "Hof Gruber" in email.subject


# ── Members ─────────────────────────────────────────────────────────────────


def test_members_and_roles(anna: tuple[TestClient, str], new_client: Client) -> None:
    admin, farm_id = anna
    join(new_client, admin, farm_id, "wolf@example.at", "worker")
    join(new_client, admin, farm_id, "berta@example.at", "advisor")

    members = admin.get(f"/api/farms/{farm_id}/members").json()

    assert [(m["user"]["email"], m["role"], m["assignable"]) for m in members] == [
        ("anna@example.at", "admin", True),
        ("berta@example.at", "advisor", False),
        ("wolf@example.at", "worker", True),
    ]


def test_the_farm_always_keeps_an_admin(anna: tuple[TestClient, str], new_client: Client) -> None:
    admin, farm_id = anna
    me = admin.get("/api/me").json()["user"]["id"]
    worker = join(new_client, admin, farm_id, "wolf@example.at", "worker")
    wolf = worker.get("/api/me").json()["user"]["id"]

    for attempt in (
        admin.patch(f"/api/farms/{farm_id}/members/{me}", json={"role": "worker"}),
        admin.delete(f"/api/farms/{farm_id}/members/{me}"),
    ):
        assert (attempt.status_code, attempt.json()["detail"]) == (409, "last_admin")

    assert (
        admin.patch(f"/api/farms/{farm_id}/members/{wolf}", json={"role": "admin"}).status_code
        == 200
    )
    assert (
        admin.patch(f"/api/farms/{farm_id}/members/{me}", json={"role": "worker"}).status_code
        == 200
    )
    assert admin.get(f"/api/farms/{farm_id}").json()["role"] == "worker"


def test_removing_and_leaving(anna: tuple[TestClient, str], new_client: Client) -> None:
    admin, farm_id = anna
    worker = join(new_client, admin, farm_id, "wolf@example.at", "worker")
    advisor = join(new_client, admin, farm_id, "berta@example.at", "advisor")
    anna_id = admin.get("/api/me").json()["user"]["id"]
    berta_id = advisor.get("/api/me").json()["user"]["id"]
    wolf_id = worker.get("/api/me").json()["user"]["id"]

    assert worker.delete(f"/api/farms/{farm_id}/members/{berta_id}").status_code == 403
    assert worker.delete(f"/api/farms/{farm_id}/members/{wolf_id}").status_code == 204
    assert worker.get(f"/api/farms/{farm_id}").status_code == 404
    assert admin.delete(f"/api/farms/{farm_id}/members/{berta_id}").status_code == 204
    alone = admin.delete(f"/api/farms/{farm_id}/members/{anna_id}")
    assert (alone.status_code, alone.json()["detail"]) == (409, "last_member")


def test_losing_the_right_to_complete_work_unassigns_it(
    anna: tuple[TestClient, str], new_client: Client
) -> None:
    admin, farm_id = anna
    worker = join(new_client, admin, farm_id, "wolf@example.at", "worker")
    wolf_id = worker.get("/api/me").json()["user"]["id"]
    task = admin.post(
        f"/api/farms/{farm_id}/tasks", json={"title": "Säen", "assignee_id": wolf_id}
    ).json()

    admin.patch(f"/api/farms/{farm_id}/members/{wolf_id}", json={"role": "advisor"})

    assert admin.get(f"/api/farms/{farm_id}/tasks/{task['id']}").json()["assignee"] is None


# ── Account deletion ────────────────────────────────────────────────────────


def test_deleting_an_account(anna: tuple[TestClient, str], new_client: Client, db: Session) -> None:
    admin, farm_id = anna
    worker = join(new_client, admin, farm_id, "wolf@example.at", "worker")
    worker.post("/api/farms", json={"name": "Wolfs Hof"})
    done = worker.post(
        f"/api/farms/{farm_id}/tasks", json={"title": "Traktor-Service", "done": True}
    ).json()

    wrong = worker.request("DELETE", "/api/me", json={"password": "nope"})
    assert (wrong.status_code, wrong.json()["detail"]) == (403, "wrong_password")

    deleted = worker.request("DELETE", "/api/me", json={"password": PASSWORD})

    assert deleted.status_code == 204
    assert worker.get("/api/me").status_code == 401
    assert db.scalar(select(Farm).where(Farm.name == "Wolfs Hof")) is None
    record = admin.get(f"/api/farms/{farm_id}/tasks/{done['id']}").json()
    assert (record["status"], record["completed_by"]) == ("done", None)
    assert (
        worker.post(
            "/api/auth/sign-in", json={"email": "wolf@example.at", "password": PASSWORD}
        ).status_code
        == 401
    )


def test_the_last_admin_hands_over_before_deleting_their_account(
    anna: tuple[TestClient, str], new_client: Client
) -> None:
    admin, farm_id = anna
    join(new_client, admin, farm_id, "wolf@example.at", "worker")

    blocked = admin.request("DELETE", "/api/me", json={"password": PASSWORD})

    assert blocked.status_code == 409
    assert blocked.json()["detail"] == {"code": "last_admin", "farms": ["Hof Gruber"]}
    assert admin.get("/api/me").status_code == 200
