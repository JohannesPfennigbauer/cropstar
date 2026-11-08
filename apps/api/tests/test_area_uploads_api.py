import json
from dataclasses import replace
from typing import Any

import httpx2
import pytest

from cropstar_api.routes import area_uploads
from tests.eama_export import demo_export, demo_rows, fields_set, plots_set, zipped
from tests.farm_fixtures import Areas, Farm, Person, create


def upload(
    person: Person,
    farm: Farm,
    files: dict[str, bytes],
    *,
    preview: bool,
    assignments: dict[str, str | None] | None = None,
) -> httpx2.Response:
    suffix = "/preview" if preview else ""
    data = {}
    if assignments is not None:
        data["assignments"] = json.dumps(
            [{"key": key, "target": target} for key, target in assignments.items()]
        )
    return person.client.post(
        f"/api/farms/{farm.id}/area-uploads{suffix}",
        files=[
            ("files", (name, content, "application/octet-stream"))
            for name, content in files.items()
        ],
        data=data,
    )


def decisions(
    preview: dict[str, Any], kind: str = "plots"
) -> dict[str, tuple[str, tuple[str, ...]]]:
    return {
        feature["id"]: (
            feature["properties"]["decision"]["status"],
            tuple(feature["properties"]["decision"]["changes"]),
        )
        for feature in preview[kind]["features"]
    }


def uploaded_2026(farm: Farm) -> dict[tuple[int, int], str]:
    """Upload the demo export into 2026; the Plot ids by Field and Plot number."""
    assert upload(farm.admin, farm, demo_export(2026), preview=False).status_code == 200
    return {
        (
            p["field"]["number"],
            p["number"],
        ): p["id"]
        for p in areas_of(farm.admin, farm, "plots", 2026)
    }


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
    assert set(decisions(preview).values()) == {("new", ())}
    assert preview["current_plots"]["features"] == []
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

    assert response.status_code == 200, response.text
    assert response.json() == {
        "harvest_year": 2025,
        "field_count": 2,
        "plot_count": 4,
        "created_count": 6,
        "changed_count": 0,
        "removed_count": 0,
    }
    assert years(farm.worker, farm) == [2025]
    fields = areas_of(farm.worker, farm, "fields", 2025)
    assert [
        (
            f["number"],
            f["name"],
            f["plot_count"],
        )
        for f in fields
    ] == [
        (1, "Kellerberg", 2),
        (2, "Am Graben", 2),
    ]
    plots = areas_of(farm.advisor, farm, "plots", 2025)
    assert [
        (
            p["field"]["number"],
            p["number"],
            p["land_use_name"],
        )
        for p in plots
    ] == [
        (1, 1, "WINTERROGGEN"),
        (1, 2, "GRÜNBRACHE"),
        (2, 1, "SONNENBLUMEN"),
        (2, 2, "SOMMERGERSTE"),
    ]
    assert plots[0]["declared_area_ha"] == 4.8094
    assert {p["provenance"]["source"] for p in [*fields, *plots]} == {"eama_export"}


def test_re_uploading_the_same_export_changes_nothing_and_keeps_operations(farm: Farm) -> None:
    plots = uploaded_2026(farm)
    task = create(
        farm.worker, farm, title="Striegeln", operation_type="tillage", plot_ids=[plots[1, 1]]
    )

    preview = upload(farm.admin, farm, demo_export(2026), preview=True).json()
    applied = upload(farm.admin, farm, demo_export(2026), preview=False)

    assert set(decisions(preview).values()) == {("unchanged", ())}
    assert set(decisions(preview, "fields").values()) == {("unchanged", ())}
    assert preview["blockers"] == []
    assert applied.status_code == 200, applied.text
    assert applied.json()["created_count"] == applied.json()["removed_count"] == 0
    assert areas_of(farm.admin, farm, "plots", 2026)[0]["id"] == plots[1, 1]
    operations = farm.admin.client.get(f"/api/farms/{farm.id}/tasks/{task['id']}").json()
    assert [o["plot"]["id"] for o in operations["operations"]] == [plots[1, 1]]


def test_changes_are_shown_and_applied_in_place(farm: Farm) -> None:
    plots = uploaded_2026(farm)
    fields, rows = demo_rows()
    # Field 1's two Plots swap numbers; Field 2's first Plot gets another Land Use.
    rows[0], rows[1] = replace(rows[0], number=2), replace(rows[1], number=1)
    rows[2] = replace(rows[2], land_use_code="311", land_use_name="KÖRNERMAIS")
    export = fields_set(fields) | plots_set(rows)

    preview = upload(farm.admin, farm, export, preview=True).json()
    applied = upload(farm.admin, farm, export, preview=False)

    assert decisions(preview) == {
        "plot-1-2": ("changed", ("number",)),
        "plot-1-1": ("changed", ("number",)),
        "plot-2-1": ("changed", ("land_use",)),
        "plot-2-2": ("unchanged", ()),
    }
    assert applied.status_code == 200, applied.text
    now = {
        (
            p["field"]["number"],
            p["number"],
        ): (p["id"], p["land_use_name"])
        for p in areas_of(farm.admin, farm, "plots", 2026)
    }
    assert now[1, 2][0] == plots[1, 1]
    assert now[1, 1][0] == plots[1, 2]
    assert now[2, 1] == (plots[2, 1], "KÖRNERMAIS")


def test_areas_on_new_ground_wait_for_a_decision(farm: Farm) -> None:
    plots = uploaded_2026(farm)
    fields, rows = demo_rows()
    # Plot 2/2 now lies on ground no existing Plot covers.
    shifted = [[[x + 5_000, y] for x, y in ring] for ring in rows[3].rings]
    rows[3] = replace(rows[3], rings=shifted)
    export = fields_set(fields) | plots_set(rows)

    preview = upload(farm.admin, farm, export, preview=True).json()
    undecided = upload(farm.admin, farm, export, preview=False)
    as_new = upload(farm.admin, farm, export, preview=True, assignments={"plot-2-2": None})
    as_before = upload(
        farm.admin, farm, export, preview=False, assignments={"plot-2-2": plots[2, 2]}
    )

    assert decisions(preview)["plot-2-2"] == ("undecided", ())
    assert preview["blockers"] == ["undecided_areas"]
    removed = [f["id"] for f in preview["current_plots"]["features"] if f["properties"]["removed"]]
    assert removed == [plots[2, 2]]
    assert (undecided.status_code, undecided.json()["detail"]) == (409, "undecided_areas")
    assert decisions(as_new.json())["plot-2-2"] == ("new", ())
    assert as_new.json()["blockers"] == []
    assert as_before.status_code == 200, as_before.text
    assert as_before.json()["changed_count"] == 1


def test_removing_a_plot_with_tasks_is_refused_and_names_the_tasks(farm: Farm) -> None:
    plots = uploaded_2026(farm)
    task = create(farm.worker, farm, title="Zaun reparieren", plot_ids=[plots[2, 2]])
    fields, rows = demo_rows()
    export = fields_set(fields) | plots_set(rows[:3])

    preview = upload(farm.admin, farm, export, preview=True).json()
    applied = upload(farm.admin, farm, export, preview=False)

    assert preview["blockers"] == ["removes_referenced_areas"]
    removed = [f for f in preview["current_plots"]["features"] if f["properties"]["removed"]]
    assert [(f["id"], f["properties"]["tasks"]) for f in removed] == [
        (plots[2, 2], [{"id": task["id"], "title": "Zaun reparieren"}])
    ]
    assert (applied.status_code, applied.json()["detail"]) == (409, "removes_referenced_areas")
    assert len(areas_of(farm.admin, farm, "plots", 2026)) == 4


def test_a_plot_assigned_on_another_field_moves_there_with_its_operations(farm: Farm) -> None:
    plots = uploaded_2026(farm)
    task = create(
        farm.worker, farm, title="Striegeln", operation_type="tillage", plot_ids=[plots[1, 2]]
    )
    fields, rows = demo_rows()
    # Plot 1/2 is declared as Plot 3 of Field 2.
    rows[1] = replace(rows[1], field_number=2, number=3)
    export = fields_set(fields) | plots_set(rows)

    preview = upload(farm.admin, farm, export, preview=True).json()
    applied = upload(farm.admin, farm, export, preview=False)

    assert decisions(preview)["plot-2-3"] == ("changed", ("number", "field"))
    assert applied.status_code == 200, applied.text
    moved = farm.admin.client.get(f"/api/farms/{farm.id}/plots/{plots[1, 2]}").json()
    assert (
        moved["properties"]["field"]["number"],
        moved["properties"]["number"],
    ) == (2, 3)
    log = farm.admin.client.get(f"/api/farms/{farm.id}/tasks/{task['id']}").json()
    assert [o["plot"]["id"] for o in log["operations"]] == [plots[1, 2]]


def test_removed_fields_take_their_unassigned_plots_along(farm: Farm) -> None:
    plots = uploaded_2026(farm)
    fields, rows = demo_rows()
    # Field 2 is gone; its first Plot now belongs to Field 1, its second is gone too.
    export = fields_set(fields[:1]) | plots_set(
        [*rows[:2], replace(rows[2], field_number=1, number=3)]
    )

    applied = upload(farm.admin, farm, export, preview=False)

    assert applied.status_code == 200, applied.text
    assert applied.json()["removed_count"] == 2
    assert [f["number"] for f in areas_of(farm.admin, farm, "fields", 2026)] == [1]
    remaining = {
        (p["field"]["number"], p["number"]): p["id"]
        for p in areas_of(farm.admin, farm, "plots", 2026)
    }
    assert remaining == {(1, 1): plots[1, 1], (1, 2): plots[1, 2], (1, 3): plots[2, 1]}


@pytest.mark.parametrize(
    "assignments",
    ["not json", json.dumps([{"key": "plot-9-9", "target": None}])],
)
def test_invalid_assignments_are_refused(farm: Farm, assignments: str) -> None:
    response = farm.admin.client.post(
        f"/api/farms/{farm.id}/area-uploads/preview",
        files=[("files", (n, c, "application/octet-stream")) for n, c in demo_export().items()],
        data={"assignments": assignments},
    )

    assert (response.status_code, response.json()["detail"]) == (422, "invalid_assignments")


def test_a_locked_harvest_year_is_refused(farm: Farm, areas: Areas) -> None:
    assert farm.admin.client.put(f"/api/farms/{farm.id}/harvest-years/2026/lock").is_success

    preview = upload(farm.admin, farm, demo_export(2026), preview=True)
    applied = upload(farm.admin, farm, demo_export(2026), preview=False)

    assert preview.json()["blockers"][0] == "harvest_year_locked"
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


def test_uploaded_plots_are_linked_to_the_same_ground_a_year_before(farm: Farm) -> None:
    before = uploaded_2026(farm)
    assert upload(farm.admin, farm, demo_export(2027), preview=False).status_code == 200
    plot = next(p for p in areas_of(farm.admin, farm, "plots", 2027) if p["number"] == 1)

    lineage = farm.admin.client.get(f"/api/farms/{farm.id}/plots/{plot['id']}/lineage").json()

    field_number = plot["field"]["number"]
    assert [(p["id"], p["harvest_year"], p["overlap"]) for p in lineage] == [
        (before[field_number, 1], 2026, 1.0)
    ]
