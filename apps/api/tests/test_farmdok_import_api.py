import json
from typing import Any

import httpx2
import pytest

from tests.eama_export import demo_export
from tests.farm_fixtures import Farm, Person, create
from tests.farmdok_export import DEMO_ROWS, Row, field_list


def send(
    person: Person,
    farm: Farm,
    content: bytes,
    *,
    preview: bool,
    reference_year: int | None = None,
    crops: dict[str, str] | None = None,
) -> httpx2.Response:
    data: dict[str, str] = {}
    if reference_year is not None:
        data["reference_year"] = str(reference_year)
    if crops is not None:
        data["crop_assignments"] = json.dumps(crops)
    suffix = "/preview" if preview else ""
    return person.client.post(
        f"/api/farms/{farm.id}/imports/farmdok-field-list{suffix}",
        files=[("file", ("Feldstücksliste_2025.xls", content, "application/vnd.ms-excel"))],
        data=data,
    )


def upload_eama(farm: Farm, year: int) -> None:
    response = farm.admin.client.post(
        f"/api/farms/{farm.id}/area-uploads",
        files=[("files", (n, c, "application/octet-stream")) for n, c in demo_export(year).items()],
    )
    assert response.status_code == 200, response.text


def plots_of(person: Person, farm: Farm, year: int) -> list[dict[str, Any]]:
    response = person.client.get(f"/api/farms/{farm.id}/plots", params={"harvest_year": year})
    return [{**f["properties"], "geometry": f["geometry"]} for f in response.json()["features"]]


def test_the_preview_borrows_geometry_from_the_nearest_eama_year(farm: Farm) -> None:
    upload_eama(farm, 2026)
    rows = (*DEMO_ROWS, Row(3, "Neu", 1, "Grünbrache", 1.0))

    preview = send(farm.admin, farm, field_list(rows), preview=True).json()

    assert (preview["harvest_year"], preview["reference_year"]) == (2025, 2026)
    assert preview["reference_years"] == [2026]
    assert preview["blockers"] == []
    assert preview["geometry_counts"] == {"plot": 4, "area": 0, "field": 0, "none": 1}
    plots = preview["plots"]["features"]
    assert plots[0]["geometry"]["type"] == "MultiPolygon"
    assert plots[-1]["geometry"] is None
    assert plots[0]["properties"]["land_use_code"] == "142"


def test_importing_creates_provisional_areas_as_one_batch(farm: Farm) -> None:
    upload_eama(farm, 2026)
    rows = (*DEMO_ROWS, Row(3, "Neu", 1, "Grünbrache", 1.0))

    response = send(farm.admin, farm, field_list(rows), preview=False)

    assert response.status_code == 201, response.text
    batch = response.json()
    assert (batch["harvest_year"], batch["field_count"], batch["plot_count"]) == (2025, 3, 5)
    assert batch["source_name"] == "Feldstücksliste_2025.xls"
    plots = plots_of(farm.worker, farm, 2025)
    assert [p["provenance"]["source"] for p in plots] == ["borrowed"] * 4 + ["none"]
    assert plots[0]["provenance"]["borrowed_from_year"] == 2026
    assert plots[-1]["geometry"] is None
    batches = farm.admin.client.get(f"/api/farms/{farm.id}/import-batches").json()
    assert [b["id"] for b in batches] == [batch["id"]]


def test_unknown_crops_wait_for_an_assignment(farm: Farm) -> None:
    rows = (*DEMO_ROWS, Row(3, "Rain", 1, "Sonstige Grünlandfläche", 0.1))

    preview = send(farm.admin, farm, field_list(rows), preview=True).json()
    refused = send(farm.admin, farm, field_list(rows), preview=False)
    assigned = send(
        farm.admin, farm, field_list(rows), preview=False, crops={"Sonstige Grünlandfläche": "361"}
    )

    assert preview["unknown_crops"] == [{"name": "Sonstige Grünlandfläche", "plot_count": 1}]
    assert preview["blockers"] == ["unknown_crops"]
    # No eAMA year to borrow from: everything is imported without geometry.
    assert preview["reference_year"] is None
    assert (refused.status_code, refused.json()["detail"]) == (409, "unknown_crops")
    assert assigned.status_code == 201, assigned.text
    land_uses = {p["land_use_name"] for p in plots_of(farm.admin, farm, 2025)}
    assert "GLÖZ RAIN / BÖSCHUNG / TROCKENSTEINMAUER" in land_uses


def test_a_year_with_areas_or_a_lock_is_refused(farm: Farm) -> None:
    upload_eama(farm, 2025)
    assert farm.admin.client.put(f"/api/farms/{farm.id}/harvest-years/2025/lock").is_success

    preview = send(farm.admin, farm, field_list(), preview=True).json()

    assert preview["blockers"] == ["harvest_year_locked", "harvest_year_not_empty"]


def test_undo_removes_the_import_until_tasks_use_it(farm: Farm) -> None:
    batch = send(farm.admin, farm, field_list(), preview=False).json()
    plot = plots_of(farm.admin, farm, 2025)[0]
    task = create(farm.worker, farm, title="Zaun", plot_ids=[plot["id"]])
    url = f"/api/farms/{farm.id}/import-batches/{batch['id']}"

    in_use = farm.admin.client.delete(url)
    farm.admin.client.delete(f"/api/farms/{farm.id}/tasks/{task['id']}")
    undone = farm.admin.client.delete(url)

    assert (in_use.status_code, in_use.json()["detail"]) == (409, "import_in_use")
    assert undone.status_code == 204
    assert plots_of(farm.admin, farm, 2025) == []
    assert farm.admin.client.get(f"/api/farms/{farm.id}/import-batches").json() == []


def test_undo_is_refused_for_a_locked_year(farm: Farm) -> None:
    batch = send(farm.admin, farm, field_list(), preview=False).json()
    farm.admin.client.put(f"/api/farms/{farm.id}/harvest-years/2025/lock")

    response = farm.admin.client.delete(f"/api/farms/{farm.id}/import-batches/{batch['id']}")

    assert (response.status_code, response.json()["detail"]) == (409, "harvest_year_locked")


def test_an_eama_upload_replaces_borrowed_geometry(farm: Farm) -> None:
    upload_eama(farm, 2026)
    send(farm.admin, farm, field_list(), preview=False)
    before = {
        (p["field"]["number"], p["number"]): p["id"] for p in plots_of(farm.admin, farm, 2025)
    }

    upload_eama(farm, 2025)

    after = plots_of(farm.admin, farm, 2025)
    assert {(p["field"]["number"], p["number"]): p["id"] for p in after} == before
    assert {p["provenance"]["source"] for p in after} == {"eama_export"}
    assert {p["provenance"]["borrowed_from_year"] for p in after} == {None}


@pytest.mark.parametrize("preview", [True, False])
def test_only_admins_import(farm: Farm, preview: bool) -> None:
    for person in (farm.worker, farm.advisor):
        response = send(person, farm, field_list(), preview=preview)
        assert (response.status_code, response.json()["detail"]) == (403, "forbidden_for_role")


def test_only_admins_undo(farm: Farm) -> None:
    batch = send(farm.admin, farm, field_list(), preview=False).json()

    response = farm.worker.client.delete(f"/api/farms/{farm.id}/import-batches/{batch['id']}")

    assert (response.status_code, response.json()["detail"]) == (403, "forbidden_for_role")


def test_unreadable_reports_list_their_problems(farm: Farm) -> None:
    response = send(farm.admin, farm, b"not a spreadsheet", preview=True)

    assert response.status_code == 422
    assert response.json()["detail"]["problems"][0]["code"] == "unreadable_file"


def test_a_reference_year_must_have_an_eama_export(farm: Farm) -> None:
    response = send(farm.admin, farm, field_list(), preview=True, reference_year=2019)

    assert (response.status_code, response.json()["detail"]) == (422, "invalid_reference_year")
