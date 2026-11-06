import json
from typing import Any

import httpx2
import pytest

from tests.farm_fixtures import Farm, Person
from tests.farmdok_export import DEMO_ENTRIES, DEMO_ROWS, Entry, Row, crop_log, field_list


def send(
    person: Person,
    farm: Farm,
    content: bytes,
    *,
    preview: bool,
    resolutions: dict[str, Any] | None = None,
) -> httpx2.Response:
    data = {"resolutions": json.dumps(resolutions)} if resolutions is not None else {}
    suffix = "/preview" if preview else ""
    return person.client.post(
        f"/api/farms/{farm.id}/imports/farmdok-crop-log{suffix}",
        files=[("file", ("Pflanzenbaujournal_2025.xls", content, "application/vnd.ms-excel"))],
        data=data,
    )


def import_field_list(farm: Farm) -> None:
    response = farm.admin.client.post(
        f"/api/farms/{farm.id}/imports/farmdok-field-list",
        files=[("file", ("Feldstücksliste.xls", field_list(), "application/vnd.ms-excel"))],
    )
    assert response.status_code == 201, response.text


def add_input(farm: Farm, body: dict[str, Any]) -> Any:
    response = farm.admin.client.post(f"/api/farms/{farm.id}/farm-inputs", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def done_tasks(person: Person, farm: Farm) -> list[dict[str, Any]]:
    response = person.client.get(f"/api/farms/{farm.id}/tasks", params={"status": "done"})
    tasks: list[dict[str, Any]] = response.json()
    return tasks


@pytest.fixture
def ready(farm: Farm) -> Farm:
    """2025's areas from farmdok, and the Farm Inputs the demo log names."""
    import_field_list(farm)
    add_input(farm, {"kind": "fertiliser", "name": "Rindermist", "unit": "m3"})
    add_input(farm, {"kind": "seed", "name": "Winterroggen", "land_use_code": "142"})
    return farm


def test_the_preview_lists_the_tasks_it_would_create(ready: Farm) -> None:
    preview = send(ready.admin, ready, crop_log(), preview=True).json()

    assert preview["blockers"] == []
    assert (preview["entry_count"], len(preview["tasks"]), preview["operation_count"]) == (5, 5, 5)
    manure = preview["tasks"][0]
    assert (manure["title"], manure["operation_type"], manure["farm_input_name"]) == (
        "Wirtschaftsdünger Mist",
        "fertilisation",
        "Rindermist",
    )
    assert [(p["field_number"], p["number"]) for p in preview["tasks"][1]["plots"]] == [(1, 1)]


def test_importing_creates_done_tasks_marked_as_imported(ready: Farm) -> None:
    response = send(ready.admin, ready, crop_log(), preview=False)

    assert response.status_code == 201, response.text
    assert response.json()["task_count"] == 5
    tasks = done_tasks(ready.worker, ready)
    harvest = next(t for t in tasks if t["title"] == "Mähdrusch")
    assert harvest["imported"]["kind"] == "farmdok_crop_log"
    operation = harvest["operations"][0]
    assert (operation["status"], operation["performed_on"]) == ("done", "2025-07-20")
    assert operation["actual_details"]["yield_t_per_ha"] == 5.432
    manure = next(t for t in tasks if t["operation_type"] == "fertilisation")
    assert manure["operations"][0]["actual_input"]["farm_input"]["name"] == "Rindermist"


def test_a_second_import_of_the_year_is_refused(ready: Farm) -> None:
    send(ready.admin, ready, crop_log(), preview=False)

    again = send(ready.admin, ready, crop_log(), preview=False)

    assert (again.status_code, again.json()["detail"]) == (409, "already_imported")


def test_unresolved_entries_are_listed_and_answers_remembered(farm: Farm) -> None:
    import_field_list(farm)
    entries = (
        Entry("01.05.2025", "1", "Winterroggen", "Spatenrollegge"),
        Entry("02.05.2025", "1", "Winterroggen", "Wirtschaftsdünger Mist", "Kompost", 10.0, "t/ha"),
        Entry("03.05.2025", "9", "Winterroggen", "Striegeln"),
    )

    preview = send(farm.admin, farm, crop_log(entries), preview=True).json()
    resolved = send(
        farm.admin,
        farm,
        crop_log(entries),
        preview=False,
        resolutions={
            "activities": {"Spatenrollegge": "tillage"},
            "products": {"Kompost": {"create": True}},
            "entries": {"9": None},
        },
    )

    assert preview["blockers"] == ["unresolved"]
    assert {(u["problem"], u["key"]) for u in preview["unresolved"]} == {
        ("unknown_activity", "Spatenrollegge"),
        ("unknown_product", "Kompost"),
        ("unknown_field", "9"),
    }
    product = next(u for u in preview["unresolved"] if u["problem"] == "unknown_product")
    assert (product["input_kind"], product["can_create"]) == ("fertiliser", True)
    assert resolved.status_code == 201, resolved.text
    inputs = farm.admin.client.get(f"/api/farms/{farm.id}/farm-inputs").json()
    assert [(i["name"], i["unit"]) for i in inputs] == [("Kompost", "t")]

    # Next year's log: the answers are remembered.
    later = send(farm.admin, farm, crop_log(entries[:2], year=2025), preview=True).json()
    assert later["unresolved"] == []


def test_remembered_crops_from_the_field_list_find_the_plots(farm: Farm) -> None:
    rows = (*DEMO_ROWS, Row(3, "Rain", 1, "Sonstige Grünlandfläche", 0.1))
    farm.admin.client.post(
        f"/api/farms/{farm.id}/imports/farmdok-field-list",
        files=[("file", ("F.xls", field_list(rows), "application/vnd.ms-excel"))],
        data={"crop_assignments": json.dumps({"Sonstige Grünlandfläche": "361"})},
    )
    entries = (Entry("01.06.2025", "3", "Sonstige Grünlandfläche", "Schlägeln/Mulchen"),)

    preview = send(farm.admin, farm, crop_log(entries), preview=True).json()

    assert preview["unresolved"] == []
    assert [p["field_number"] for p in preview["tasks"][0]["plots"]] == [3]


def test_undo_until_the_imported_work_is_edited(ready: Farm) -> None:
    batch = send(ready.admin, ready, crop_log(), preview=False).json()
    url = f"/api/farms/{ready.id}/import-batches/{batch['id']}"
    task = done_tasks(ready.admin, ready)[0]

    ready.worker.client.patch(f"/api/farms/{ready.id}/tasks/{task['id']}", json={"title": "x"})
    edited = ready.admin.client.delete(url)

    assert (edited.status_code, edited.json()["detail"]) == (409, "import_edited")


def test_undo_removes_the_tasks_but_keeps_farm_inputs(ready: Farm) -> None:
    batch = send(ready.admin, ready, crop_log(), preview=False).json()

    response = ready.admin.client.delete(f"/api/farms/{ready.id}/import-batches/{batch['id']}")

    assert response.status_code == 204
    assert done_tasks(ready.admin, ready) == []
    assert len(ready.admin.client.get(f"/api/farms/{ready.id}/farm-inputs").json()) == 2


def test_only_admins_import_logs(ready: Farm) -> None:
    for person in (ready.worker, ready.advisor):
        response = send(person, ready, crop_log(), preview=True)
        assert (response.status_code, response.json()["detail"]) == (403, "forbidden_for_role")


@pytest.mark.parametrize(
    "resolutions",
    [
        {"activities": {"Hexen": "tillage"}},
        {"products": {"Rindermist": {"create": True, "none": True}}},
        {"entries": {"99": None}},
        "not json",
    ],
)
def test_invalid_resolutions_are_refused(ready: Farm, resolutions: Any) -> None:
    raw = resolutions if isinstance(resolutions, str) else json.dumps(resolutions)
    response = ready.admin.client.post(
        f"/api/farms/{ready.id}/imports/farmdok-crop-log/preview",
        files=[("file", ("J.xls", crop_log(), "application/vnd.ms-excel"))],
        data={"resolutions": raw},
    )

    assert (response.status_code, response.json()["detail"]) == (422, "invalid_resolutions")


def test_a_field_list_is_not_a_log(ready: Farm) -> None:
    response = send(ready.admin, ready, field_list(), preview=True)

    assert response.json()["detail"]["problems"][0]["code"] == "not_a_crop_log"


def test_entries_by_hand_and_skipped_ones(ready: Farm) -> None:
    preview = send(ready.admin, ready, crop_log(DEMO_ENTRIES[:1]), preview=True).json()
    plots = preview["plots"]

    result = send(
        ready.admin,
        ready,
        crop_log(DEMO_ENTRIES[:2]),
        preview=True,
        resolutions={"entries": {"7": [plots[2]["id"]], "8": None}},
    ).json()

    assert [[p["id"] for p in t["plots"]] for t in result["tasks"]] == [[plots[2]["id"]]]
    assert result["skipped_rows"] == [8]
