from typing import Any

import httpx2
import pytest

from cropstar_api.routes import area_uploads
from tests.eama_export import demo_export, zipped
from tests.farm_fixtures import Areas, Farm, Person


def upload(
    person: Person, farm: Farm, files: dict[str, bytes], *, preview: bool
) -> httpx2.Response:
    suffix = "/preview" if preview else ""
    return person.client.post(
        f"/api/farms/{farm.id}/area-uploads{suffix}",
        files=[
            ("files", (name, content, "application/octet-stream"))
            for name, content in files.items()
        ],
    )


def areas_of(person: Person, farm: Farm, kind: str, year: int) -> list[dict[str, Any]]:
    response = person.client.get(f"/api/farms/{farm.id}/{kind}", params={"harvest_year": year})
    assert response.status_code == 200, response.text
    return [feature["properties"] for feature in response.json()["features"]]


def years(person: Person, farm: Farm) -> list[int]:
    return [
        entry["year"] for entry in person.client.get(f"/api/farms/{farm.id}/harvest-years").json()
    ]


def test_preview_shows_the_export_in_wgs84_and_writes_nothing(farm: Farm) -> None:
    response = upload(farm.admin, farm, demo_export(2025), preview=True)

    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["harvest_year"] == 2025
    assert preview["blockers"] == []
    assert preview["field_area_ha"] == pytest.approx(5.2504 + 3.4534)
    assert preview["plot_area_ha"] == pytest.approx(4.8094 + 0.441 + 2.7669 + 0.6865)
    assert [f["properties"]["name"] for f in preview["fields"]["features"]] == [
        "Kellerberg",
        "Am Graben",
    ]
    plot = preview["plots"]["features"][1]
    assert plot["properties"]["land_use_name"] == "GRÜNBRACHE"
    assert plot["properties"]["land_use_category"] == "fallow"
    lon, lat = plot["geometry"]["coordinates"][0][0][0]
    assert 9 < lon < 18 and 46 < lat < 49.5
    assert years(farm.admin, farm) == []


def test_confirming_creates_the_harvest_year_with_its_provenance(farm: Farm) -> None:
    response = upload(farm.admin, farm, {"export.zip": zipped(demo_export(2025))}, preview=False)

    assert response.status_code == 201, response.text
    assert response.json() == {"harvest_year": 2025, "field_count": 2, "plot_count": 4}
    assert years(farm.worker, farm) == [2025]
    fields = areas_of(farm.worker, farm, "fields", 2025)
    assert [(f["number"], f["name"], f["plot_count"]) for f in fields] == [
        (1, "Kellerberg", 2),
        (2, "Am Graben", 2),
    ]
    plots = areas_of(farm.advisor, farm, "plots", 2025)
    assert [(p["field"]["number"], p["number"], p["land_use_name"]) for p in plots] == [
        (1, 1, "WINTERROGGEN"),
        (1, 2, "GRÜNBRACHE"),
        (2, 1, "SONNENBLUMEN"),
        (2, 2, "SOMMERGERSTE"),
    ]
    assert plots[0]["declared_area_ha"] == 4.8094
    assert {p["provenance"]["source"] for p in [*fields, *plots]} == {"eama_export"}


def test_a_harvest_year_with_areas_is_refused(farm: Farm, areas: Areas) -> None:
    preview = upload(farm.admin, farm, demo_export(2026), preview=True)
    assert preview.json()["blockers"] == ["harvest_year_not_empty"]

    applied = upload(farm.admin, farm, demo_export(2026), preview=False)

    assert (applied.status_code, applied.json()["detail"]) == (409, "harvest_year_not_empty")
    assert len(areas_of(farm.admin, farm, "plots", 2026)) == 1


def test_a_locked_harvest_year_is_refused(farm: Farm, areas: Areas) -> None:
    assert farm.admin.client.put(f"/api/farms/{farm.id}/harvest-years/2026/lock").is_success

    preview = upload(farm.admin, farm, demo_export(2026), preview=True)
    applied = upload(farm.admin, farm, demo_export(2026), preview=False)

    assert preview.json()["blockers"] == ["harvest_year_locked", "harvest_year_not_empty"]
    assert (applied.status_code, applied.json()["detail"]) == (409, "harvest_year_locked")


@pytest.mark.parametrize("preview", [True, False])
def test_only_admins_upload(farm: Farm, preview: bool) -> None:
    for person in (farm.worker, farm.advisor):
        denied = upload(person, farm, demo_export(), preview=preview)
        assert (denied.status_code, denied.json()["detail"]) == (403, "forbidden_for_role")
    assert upload(farm.stranger, farm, demo_export(), preview=preview).status_code == 404
    assert years(farm.admin, farm) == []


def test_problems_with_the_export_are_listed(farm: Farm) -> None:
    files = {n: c for n, c in demo_export().items() if not n.endswith(".prj")}

    response = upload(farm.admin, farm, files, preview=True)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_eama_export"
    assert {(p["code"], p["file"][-4:]) for p in detail["problems"]} == {
        ("missing_component", ".prj")
    }
    assert len(detail["problems"]) == 2


def test_oversized_uploads_are_refused_before_reading(
    farm: Farm, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(area_uploads, "MAX_UPLOAD_BYTES", 1_000)

    response = upload(farm.admin, farm, demo_export(), preview=True)

    assert (response.status_code, response.json()["detail"]) == (413, "upload_too_large")
