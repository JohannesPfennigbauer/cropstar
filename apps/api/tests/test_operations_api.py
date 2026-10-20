from typing import Any

from tests.farm_fixtures import Areas, Farm, create, tasks_url


def harrow(farm: Farm, areas: Areas, **body: Any) -> Any:
    return create(
        farm.worker,
        farm,
        title="Striegeln",
        operation_type="tillage",
        planned_details="Striegel, 2 cm",
        plot_ids=[areas.plot_2027_a, areas.plot_2027_b],
        **body,
    )


def op_url(farm: Farm, task: Any, index: int, suffix: str = "") -> str:
    return tasks_url(farm, f"/{task['id']}/operations/{task['operations'][index]['id']}{suffix}")


def test_operation_types_are_global(farm: Farm) -> None:
    types = farm.advisor.client.get(f"/api/farms/{farm.id}/operation-types").json()

    assert [t["code"] for t in types] == ["tillage", "sowing", "fertilisation", "harvest"]


def test_an_operation_task_has_one_operation_per_plot(farm: Farm, areas: Areas) -> None:
    task = harrow(farm, areas)

    assert (task["operation_type"], task["status"], task["harvest_year"]) == (
        "tillage",
        "open",
        2027,
    )
    assert [
        (o["plot"]["number"], o["status"], o["planned_details"]) for o in task["operations"]
    ] == [
        (1, "open", "Striegel, 2 cm"),
        (2, "open", "Striegel, 2 cm"),
    ]
    assert task["operations"][0]["allowed_actions"] == [
        "edit_task",
        "complete_task",
        "discard_task",
    ]


def test_operation_tasks_need_plots_and_only_plots(farm: Farm, areas: Areas) -> None:
    def post(**body: Any) -> Any:
        return farm.admin.client.post(tasks_url(farm), json={"title": "Säen", **body}).json()

    assert post(operation_type="sowing")["detail"] == "operation_needs_plots"
    assert (
        post(operation_type="sowing", field_ids=[areas.field_2027], plot_ids=[areas.plot_2027_a])[
            "detail"
        ]
        == "operation_fields_not_allowed"
    )
    assert post(operation_type="spraying", plot_ids=[areas.plot_2027_a])["detail"] == (
        "unknown_operation_type"
    )


def test_completing_operations_one_by_one_and_the_operation_log(farm: Farm, areas: Areas) -> None:
    task = harrow(farm, areas)

    first = farm.worker.client.post(
        op_url(farm, task, 0, "/complete"),
        json={"actual_details": "Striegel, 3 cm", "performed_on": "2027-03-12"},
    ).json()
    assert first["status"] == "open"
    assert [o["status"] for o in first["operations"]] == ["done", "open"]

    second = farm.worker.client.post(op_url(farm, task, 1, "/complete")).json()
    assert second["status"] == "done"
    assert second["operations"][1]["actual_details"] == "Striegel, 2 cm"

    log = farm.advisor.client.get(f"/api/farms/{farm.id}/plots/{areas.plot_2027_a}/operations")
    assert [
        (e["operation_type"], e["task_title"], e["performed_on"], e["actual_details"])
        for e in log.json()
    ] == [("tillage", "Striegeln", "2027-03-12", "Striegel, 3 cm")]
    assert log.json()[0]["completed_by"]["email"] == "wolf@example.at"


def test_only_done_operations_enter_the_log(farm: Farm, areas: Areas) -> None:
    task = harrow(farm, areas)
    farm.worker.client.post(op_url(farm, task, 0, "/complete"))
    farm.worker.client.post(op_url(farm, task, 0, "/reopen"))

    log = farm.admin.client.get(f"/api/farms/{farm.id}/plots/{areas.plot_2027_a}/operations")

    assert log.json() == []


def test_adjusting_an_operation(farm: Farm, areas: Areas) -> None:
    task = harrow(farm, areas)

    adjusted = farm.advisor.client.patch(
        op_url(farm, task, 1), json={"planned_details": "Striegel, 1 cm"}
    ).json()

    assert [o["planned_details"] for o in adjusted["operations"]] == [
        "Striegel, 2 cm",
        "Striegel, 1 cm",
    ]
    assert farm.advisor.client.post(op_url(farm, task, 1, "/complete")).status_code == 403


def test_done_operations_keep_their_plot(farm: Farm, areas: Areas) -> None:
    task = harrow(farm, areas)
    farm.worker.client.post(op_url(farm, task, 0, "/complete"))

    refused = farm.worker.client.patch(
        tasks_url(farm, f"/{task['id']}"), json={"plot_ids": [areas.plot_2027_b]}
    )
    assert (refused.status_code, refused.json()["detail"]) == (409, "operation_done")

    farm.worker.client.post(op_url(farm, task, 0, "/reopen"))
    moved = farm.worker.client.patch(
        tasks_url(farm, f"/{task['id']}"), json={"plot_ids": [areas.plot_2027_b]}
    ).json()
    assert [o["plot"]["number"] for o in moved["operations"]] == [2]


def test_unknown_operations_and_type_filter(farm: Farm, areas: Areas) -> None:
    task = harrow(farm, areas)
    create(farm.worker, farm, title="Zaun")

    missing = farm.worker.client.post(
        tasks_url(farm, f"/{task['id']}/operations/00000000-0000-0000-0000-000000000000/complete")
    )
    assert (missing.status_code, missing.json()["detail"]) == (404, "operation_not_found")
    tillage = farm.worker.client.get(tasks_url(farm), params={"operation_type": "tillage"}).json()
    assert [t["title"] for t in tillage] == ["Striegeln"]
