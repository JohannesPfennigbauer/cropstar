from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from cropstar_api.models import AreaSource, Field, Plot
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


def till_and_complete(farm: Farm, plot_id: str, title: str, performed_on: str) -> None:
    task = create(
        farm.worker,
        farm,
        title=title,
        operation_type="tillage",
        planned_details=cultivate(10),
        plot_ids=[plot_id],
    )
    response = farm.worker.client.post(
        op_url(farm, task, 0, "/complete"), json={"performed_on": performed_on}
    )
    assert response.status_code == 200, response.text


def earlier_log(farm: Farm, plot_id: str) -> Any:
    return farm.advisor.client.get(
        f"/api/farms/{farm.id}/plots/{plot_id}/operations/earlier"
    ).json()


def test_earlier_harvest_years_on_the_same_ground(farm: Farm, areas: Areas) -> None:
    till_and_complete(farm, areas.plot_2026, "Grubbern", "2025-09-20")
    till_and_complete(farm, areas.plot_2027_a, "Pflügen", "2026-10-01")

    earlier = earlier_log(farm, areas.plot_2027_a)

    assert [
        (e["task_title"], e["performed_on"], e["harvest_year"], e["field_number"], e["plot_number"])
        for e in earlier
    ] == [("Grubbern", "2025-09-20", 2026, 1, 1)]
    assert earlier[0]["overlap"] > 0.95
    assert earlier_log(farm, areas.plot_2026) == []


def test_ground_covered_less_than_half_is_not_the_same(
    farm: Farm, areas: Areas, db: Session
) -> None:
    # A 2025 Plot shifted by 60 m covers only 40 % of the 2027 Plot.
    ring = "600260 502027, 600360 502027, 600360 502127, 600260 502127, 600260 502027"
    field = Field(
        farm_id=farm.id,
        harvest_year=2025,
        number=1,
        name="Feld 1",
        land_use_code="A",
        land_use_name="ACKERLAND",
        declared_area_ha=1,
        geometry=f"SRID=31287;MULTIPOLYGON((({ring})))",
        geometry_source=AreaSource.EAMA_EXPORT,
        imported_at=datetime.now(UTC),
    )
    db.add(field)
    db.flush()
    shifted = Plot(
        field_id=field.id,
        number=1,
        land_use_code="142",
        land_use_name="WINTERROGGEN",
        declared_area_ha=0.5,
        geometry=field.geometry,
        geometry_source=AreaSource.EAMA_EXPORT,
        imported_at=datetime.now(UTC),
    )
    db.add(shifted)
    db.commit()
    till_and_complete(farm, str(shifted.id), "Grubbern", "2024-09-20")

    assert earlier_log(farm, areas.plot_2027_a) == []


def test_earlier_operations_stay_within_the_farm(farm: Farm, areas: Areas) -> None:
    assert farm.stranger.client.get(
        f"/api/farms/{farm.id}/plots/{areas.plot_2027_a}/operations/earlier"
    ).status_code in (403, 404)
    assert earlier_log(farm, areas.elsewhere_plot) == []
