from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cropstar_api.app import create_app
from cropstar_api.auth.provider import PasswordAuthProvider
from cropstar_api.seed import DEMO_HARVEST_YEAR, seed_demo
from cropstar_api.settings import Settings

ANNA = {"email": "anna@example.at", "password": "correct horse"}


@pytest.fixture
def demo_farm_id(client: TestClient, db: Session) -> str:
    """Anna signed in on `client`, as Admin of the seeded demo Farm."""
    farm = seed_demo(db, PasswordAuthProvider(timedelta(days=1)), ANNA["email"], ANNA["password"])
    db.commit()
    assert client.post("/api/auth/sign-in", json=ANNA).status_code == 200
    return str(farm.id)


def get(client: TestClient, path: str) -> Any:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def test_harvest_years_lists_years_with_fields(client: TestClient, demo_farm_id: str) -> None:
    years = get(client, f"/api/farms/{demo_farm_id}/harvest-years")
    assert years == [{"year": DEMO_HARVEST_YEAR, "lock": None}]


def test_plots_come_as_wgs84_geojson_with_their_declared_attributes(
    client: TestClient, demo_farm_id: str
) -> None:
    plots = get(client, f"/api/farms/{demo_farm_id}/plots?harvest_year={DEMO_HARVEST_YEAR}")

    assert plots["type"] == "FeatureCollection"
    summary = [
        (
            f["properties"]["field"]["number"],
            f["properties"]["number"],
            f["properties"]["land_use_name"],
            f["properties"]["declared_area_ha"],
        )
        for f in plots["features"]
    ]
    assert summary == [
        (1, 1, "WINTERROGGEN", 4.8094),
        (1, 2, "GRÜNBRACHE", 0.441),
        (2, 1, "SONNENBLUMEN", 2.7669),
        (2, 2, "SOMMERGERSTE", 0.6865),
    ]


def test_geometry_is_transformed_from_ama_crs_to_wgs84(
    client: TestClient, demo_farm_id: str
) -> None:
    plots = get(client, f"/api/farms/{demo_farm_id}/plots?harvest_year={DEMO_HARVEST_YEAR}")
    rye = plots["features"][0]

    assert rye["geometry"]["type"] == "MultiPolygon"
    # EPSG:31287 (631675.18, 521536.07), the rye plot's first vertex, as computed by PostGIS.
    lon, lat = rye["geometry"]["coordinates"][0][0][0]
    assert lon == pytest.approx(16.4719674, abs=1e-6)
    assert lat == pytest.approx(48.55082, abs=1e-6)


def test_plots_carry_their_land_use_category(client: TestClient, demo_farm_id: str) -> None:
    plots = get(client, f"/api/farms/{demo_farm_id}/plots?harvest_year={DEMO_HARVEST_YEAR}")

    assert {
        f["properties"]["land_use_name"]: f["properties"]["land_use_category"]
        for f in plots["features"]
    } == {
        "WINTERROGGEN": "cereals",
        "GRÜNBRACHE": "fallow",
        "SONNENBLUMEN": "oilseeds",
        "SOMMERGERSTE": "cereals",
    }


def test_holes_survive_the_round_trip(client: TestClient, demo_farm_id: str) -> None:
    plots = get(client, f"/api/farms/{demo_farm_id}/plots?harvest_year={DEMO_HARVEST_YEAR}")
    rings = {
        f["properties"]["land_use_name"]: len(f["geometry"]["coordinates"][0])
        for f in plots["features"]
    }

    assert rings == {"WINTERROGGEN": 2, "GRÜNBRACHE": 1, "SONNENBLUMEN": 1, "SOMMERGERSTE": 2}


def test_fields_list_their_plot_count(client: TestClient, demo_farm_id: str) -> None:
    fields = get(client, f"/api/farms/{demo_farm_id}/fields?harvest_year={DEMO_HARVEST_YEAR}")

    assert [
        (f["properties"]["number"], f["properties"]["name"], f["properties"]["plot_count"])
        for f in fields["features"]
    ] == [(1, "Kellerberg", 2), (2, "Am Graben", 2)]
    assert fields["features"][0]["properties"]["land_use_code"] == "A"


def test_another_harvest_year_is_empty(client: TestClient, demo_farm_id: str) -> None:
    plots = get(client, f"/api/farms/{demo_farm_id}/plots?harvest_year=2025")

    assert plots == {"type": "FeatureCollection", "features": []}


def test_single_plot(client: TestClient, demo_farm_id: str) -> None:
    plots = get(client, f"/api/farms/{demo_farm_id}/plots?harvest_year={DEMO_HARVEST_YEAR}")
    plot_id = plots["features"][1]["id"]

    plot = get(client, f"/api/farms/{demo_farm_id}/plots/{plot_id}")

    assert plot["properties"]["land_use_name"] == "GRÜNBRACHE"
    assert plot["properties"]["harvest_year"] == DEMO_HARVEST_YEAR
    assert plot["properties"]["field"]["name"] == "Kellerberg"
    missing = client.get(f"/api/farms/{demo_farm_id}/plots/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


def test_other_farms_are_invisible(
    client: TestClient, demo_farm_id: str, settings: Settings
) -> None:
    plot_id = get(client, f"/api/farms/{demo_farm_id}/plots?harvest_year={DEMO_HARVEST_YEAR}")[
        "features"
    ][0]["id"]

    with TestClient(create_app(settings)) as stranger:
        response = stranger.post(
            "/api/auth/register",
            json={"email": "bert@example.at", "password": "correct horse", "farm_name": "Hof B"},
        )
        assert response.status_code == 201
        for path in (
            f"/api/farms/{demo_farm_id}/harvest-years",
            f"/api/farms/{demo_farm_id}/fields?harvest_year={DEMO_HARVEST_YEAR}",
            f"/api/farms/{demo_farm_id}/plots?harvest_year={DEMO_HARVEST_YEAR}",
            f"/api/farms/{demo_farm_id}/plots/{plot_id}",
        ):
            denied = stranger.get(path)
            assert denied.status_code == 404, path
            assert denied.json()["detail"] == "farm_not_found"


def test_areas_require_sign_in(client: TestClient, demo_farm_id: str) -> None:
    client.cookies.clear()

    response = client.get(f"/api/farms/{demo_farm_id}/harvest-years")

    assert response.status_code == 401
