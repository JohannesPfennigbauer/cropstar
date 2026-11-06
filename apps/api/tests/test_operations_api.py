from typing import Any

from tests.farm_fixtures import Areas, Farm, create, tasks_url


def cultivate(depth: float, **more: Any) -> dict[str, Any]:
    return {"type": "tillage", "implement": "cultivator", "depth_cm": depth, **more}


def as_returned(details: dict[str, Any]) -> dict[str, Any]:
    """Responses name every field of the details, given or not."""
    return {"implement": None, "depth_cm": None, "note": None} | details


def harrow(farm: Farm, areas: Areas, **body: Any) -> Any:
    return create(
        farm.worker,
        farm,
        title="Striegeln",
        operation_type="tillage",
        planned_details=cultivate(2),
        plot_ids=[areas.plot_2027_a, areas.plot_2027_b],
        **body,
    )


def op_url(farm: Farm, task: Any, index: int, suffix: str = "") -> str:
    return tasks_url(farm, f"/{task['id']}/operations/{task['operations'][index]['id']}{suffix}")


def test_operation_types_are_global(farm: Farm) -> None:
    types = farm.advisor.client.get(f"/api/farms/{farm.id}/operation-types").json()

    assert [t["code"] for t in types] == [
        "tillage",
        "mechanical_weed_control",
        "mulching",
        "sowing",
        "fertilisation",
        "harvest",
    ]


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
        (1, "open", as_returned(cultivate(2))),
        (2, "open", as_returned(cultivate(2))),
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
        json={"actual_details": cultivate(3, note="feucht"), "performed_on": "2027-03-12"},
    ).json()
    assert first["status"] == "open"
    assert [o["status"] for o in first["operations"]] == ["done", "open"]

    second = farm.worker.client.post(op_url(farm, task, 1, "/complete")).json()
    assert second["status"] == "done"
    assert second["operations"][1]["actual_details"] == as_returned(cultivate(2))

    log = farm.advisor.client.get(f"/api/farms/{farm.id}/plots/{areas.plot_2027_a}/operations")
    assert [
        (e["operation_type"], e["task_title"], e["performed_on"], e["actual_details"])
        for e in log.json()
    ] == [("tillage", "Striegeln", "2027-03-12", as_returned(cultivate(3, note="feucht")))]
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
        op_url(farm, task, 1), json={"planned_details": cultivate(1)}
    ).json()

    assert [o["planned_details"] for o in adjusted["operations"]] == [
        as_returned(cultivate(2)),
        as_returned(cultivate(1)),
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


def test_details_are_validated_per_operation_type(farm: Farm, areas: Areas) -> None:
    task = harrow(farm, areas)

    def plan(details: dict[str, Any], url: str | None = None) -> Any:
        target = url or tasks_url(farm, f"/{task['id']}")
        return farm.worker.client.patch(target, json={"planned_details": details})

    assert plan(cultivate(-1)).status_code == 422
    assert plan({"type": "tillage", "implement": "tine_weeder"}).status_code == 422
    mismatch = plan({"type": "harvest", "yield_t_per_ha": 6})
    assert (mismatch.status_code, mismatch.json()["detail"]) == (422, "details_type_mismatch")
    general = farm.worker.client.post(
        tasks_url(farm), json={"title": "Zaun", "planned_details": cultivate(2)}
    )
    assert (general.status_code, general.json()["detail"]) == (422, "details_need_operation_type")


def test_a_harvest_records_yield_and_quality(farm: Farm, areas: Areas) -> None:
    harvest = {
        "type": "harvest",
        "product": "grain",
        "yield_t_per_ha": 5.8,
        "moisture_percent": 14,
        "crude_protein_percent": 11.5,
        "note": None,
    }
    task = create(
        farm.worker,
        farm,
        title="Dreschen",
        operation_type="harvest",
        plot_ids=[areas.plot_2027_a],
        done=True,
        planned_details=harvest,
    )

    assert task["operations"][0]["actual_details"] == harvest
    too_much = farm.worker.client.patch(
        op_url(farm, task, 0), json={"actual_details": harvest | {"crude_protein_percent": 101}}
    )
    assert too_much.status_code == 422


def _slurry(farm: Farm) -> Any:
    response = farm.admin.client.post(
        f"/api/farms/{farm.id}/farm-inputs",
        json={
            "kind": "fertiliser",
            "name": "Rindergülle",
            "unit": "m3",
            "total_n": 3.51,
            "available_n": 2.14,
            "p2o5": 1.39,
            "k2o": 6.94,
            "value_source": "standard_value",
            "source_reference": "RSD, 8. Auflage",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_a_fertilisation_shows_the_nutrients_it_applied_with_their_source(
    farm: Farm, areas: Areas
) -> None:
    slurry = _slurry(farm)
    plan = {
        "type": "fertilisation",
        "farm_input_id": slurry["id"],
        "amount": 20,
        "unit": "m3_per_ha",
    }
    task = create(
        farm.worker,
        farm,
        title="Gülle",
        operation_type="fertilisation",
        plot_ids=[areas.plot_2027_a],
        planned_details=plan,
    )
    done = farm.worker.client.post(
        op_url(farm, task, 0, "/complete"),
        json={"actual_details": plan | {"amount": 18}, "performed_on": "2027-03-20"},
    ).json()
    farm.admin.client.post(f"/api/farms/{farm.id}/farm-inputs/{slurry['id']}/archive")
    log = farm.advisor.client.get(f"/api/farms/{farm.id}/plots/{areas.plot_2027_a}/operations")

    assert task["planned_input"]["nutrients"]["total_n"] == 70.2
    actual = done["operations"][0]["actual_input"]
    assert actual["nutrients"] == {
        "total_n": 63.2,
        "available_n": 38.5,
        "p2o5": 25.0,
        "k2o": 124.9,
        "value_source": "standard_value",
        "source_reference": "RSD, 8. Auflage",
        "analysed_on": None,
    }
    entry = log.json()[0]["actual_input"]
    assert (entry["farm_input"]["name"], entry["farm_input"]["archived"]) == ("Rindergülle", True)
    in_use = farm.admin.client.delete(f"/api/farms/{farm.id}/farm-inputs/{slurry['id']}")
    assert (in_use.status_code, in_use.json()["detail"]) == (409, "farm_input_in_use")


def test_fertiliser_references_are_checked(farm: Farm, areas: Areas) -> None:
    slurry = _slurry(farm)
    seed = farm.admin.client.post(
        f"/api/farms/{farm.id}/farm-inputs",
        json={"kind": "seed", "name": "Weizen", "land_use_code": "138"},
    ).json()

    def plan(details: dict[str, Any]) -> Any:
        return farm.worker.client.post(
            tasks_url(farm),
            json={
                "title": "Düngen",
                "operation_type": "fertilisation",
                "plot_ids": [areas.plot_2027_a],
                "planned_details": {"type": "fertilisation"} | details,
            },
        )

    mismatch = plan({"farm_input_id": slurry["id"], "amount": 20, "unit": "t_per_ha"})
    wrong_kind = plan({"farm_input_id": seed["id"]})
    unknown = plan({"farm_input_id": "00000000-0000-0000-0000-000000000000"})

    assert [(r.status_code, r.json()["detail"]) for r in (mismatch, wrong_kind, unknown)] == [
        (422, "unit_mismatch"),
        (422, "farm_input_wrong_kind"),
        (422, "farm_input_not_found"),
    ]


def test_sowing_refers_to_seed(farm: Farm, areas: Areas) -> None:
    seed = farm.admin.client.post(
        f"/api/farms/{farm.id}/farm-inputs",
        json={"kind": "seed", "name": "Weizen Capo", "land_use_code": "138"},
    ).json()

    task = create(
        farm.worker,
        farm,
        title="Säen",
        operation_type="sowing",
        plot_ids=[areas.plot_2027_a],
        planned_details={
            "type": "sowing",
            "purpose": "main_crop",
            "farm_input_id": seed["id"],
            "rate": 180,
            "unit": "kg_per_ha",
        },
    )

    assert task["planned_input"] == {
        "farm_input": {"id": seed["id"], "name": "Weizen Capo", "kind": "seed", "archived": False},
        "nutrients": None,
    }
