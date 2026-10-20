from fastapi.testclient import TestClient

from cropstar_api.app import create_app
from cropstar_api.settings import Settings


def test_liveness_needs_no_database() -> None:
    unreachable = Settings(database_url="postgresql+psycopg://nobody@127.0.0.1:1/none")
    with TestClient(create_app(unreachable)) as client:
        response = client.get("/api/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "cropstar-api"}


def test_status_reports_postgres_and_postgis_versions(client: TestClient) -> None:
    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "cropstar-api"
    assert body["database"]["reachable"] is True
    assert body["database"]["postgres_version"]
    assert body["database"]["postgis_version"]


def test_status_reports_an_unreachable_database() -> None:
    unreachable = Settings(database_url="postgresql+psycopg://nobody@127.0.0.1:1/none")
    with TestClient(create_app(unreachable)) as client:
        response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["database"] == {
        "reachable": False,
        "postgres_version": None,
        "postgis_version": None,
    }
