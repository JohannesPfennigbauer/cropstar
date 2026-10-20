import io

import pytest
from fastapi.testclient import TestClient

from cropstar_api.cli import main

ANNA = {"email": "anna@example.at", "password": "correct horse", "farm_name": "Hof Gruber"}


def run_reset(monkeypatch: pytest.MonkeyPatch, database_url: str, email: str, password: str) -> int:
    monkeypatch.setenv("CROPSTAR_DATABASE_URL", database_url)
    monkeypatch.setattr("sys.stdin", io.StringIO(password + "\n"))
    with pytest.raises(SystemExit) as exit_info:
        main(["reset-password", email, "--password-stdin"])
    return int(exit_info.value.code or 0)


def test_operator_resets_a_password_and_signs_the_user_out(
    client: TestClient, database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert client.post("/api/auth/register", json=ANNA).status_code == 201

    assert run_reset(monkeypatch, database_url, "Anna@example.at", "battery staple") == 0

    assert client.get("/api/me").status_code == 401
    signed_in = client.post(
        "/api/auth/sign-in", json={"email": ANNA["email"], "password": "battery staple"}
    )
    assert signed_in.status_code == 200


def test_reset_fails_for_unknown_users_and_short_passwords(
    database_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_reset(monkeypatch, database_url, "nobody@example.at", "battery staple") == 1
    assert "No user" in capsys.readouterr().err

    assert run_reset(monkeypatch, database_url, "nobody@example.at", "short") == 1
    assert "8 to 256" in capsys.readouterr().err
