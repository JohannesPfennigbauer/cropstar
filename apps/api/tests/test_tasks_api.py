from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from cropstar_api.models import User
from tests.farm_fixtures import Areas, Farm, create, tasks_url


def test_priority_defaults_to_none_and_blank_descriptions_are_empty(farm: Farm) -> None:
    task = create(farm.admin, farm, description="   ")

    assert (task["priority"], task["description"]) == ("none", None)


def test_title_is_required(farm: Farm) -> None:
    response = farm.admin.client.post(tasks_url(farm), json={"title": "   "})

    assert response.status_code == 422


def test_recording_work_after_the_fact(farm: Farm) -> None:
    task = create(farm.worker, farm, title="Traktor-Service", done=True)

    assert task["status"] == "done"
    assert task["completed_by"]["email"] == "wolf@example.at"
    assert task["completed_at"] is not None


def test_status_changes_and_their_order(farm: Farm) -> None:
    task_id = create(farm.worker, farm)["id"]

    def command(name: str) -> Any:
        return farm.worker.client.post(tasks_url(farm, f"/{task_id}/{name}"))

    assert command("complete").json()["status"] == "done"
    assert command("complete").status_code == 409
    reopened = command("reopen").json()
    assert (reopened["status"], reopened["completed_by"]) == ("open", None)
    assert command("discard").json()["status"] == "discarded"
    assert command("reopen").json()["detail"] == "invalid_transition"
    assert command("restore").json()["status"] == "open"
    assert command("finish").status_code == 422


def test_editing_changes_only_what_is_sent(farm: Farm) -> None:
    task = create(farm.admin, farm, description="alt", due_date="2027-04-01", priority="low")

    response = farm.advisor.client.patch(
        tasks_url(farm, f"/{task['id']}"),
        json={"title": "Zaun am Kellerberg reparieren", "due_date": None},
    )

    assert response.status_code == 200
    edited = response.json()
    assert (edited["title"], edited["description"], edited["due_date"], edited["priority"]) == (
        "Zaun am Kellerberg reparieren",
        "alt",
        None,
        "low",
    )
    for not_clearable in ({"title": None}, {"priority": None}):
        rejected = farm.admin.client.patch(tasks_url(farm, f"/{task['id']}"), json=not_clearable)
        assert rejected.status_code == 422


def test_assignees_are_admins_or_workers_of_this_farm(farm: Farm) -> None:
    task = create(farm.admin, farm, assignee_id=farm.worker.id)
    assert task["assignee"]["email"] == "wolf@example.at"

    for nobody in (farm.advisor.id, farm.stranger.id):
        response = farm.admin.client.patch(
            tasks_url(farm, f"/{task['id']}"), json={"assignee_id": nobody}
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "invalid_assignee"

    cleared = farm.admin.client.patch(tasks_url(farm, f"/{task['id']}"), json={"assignee_id": None})
    assert cleared.json()["assignee"] is None


def test_advisors_create_and_edit_but_never_change_status(farm: Farm) -> None:
    theirs = create(farm.advisor, farm, title="Bodenprobe ziehen")
    worker_task = create(farm.worker, farm)

    assert theirs["allowed_actions"] == ["edit_task", "delete_task"]
    advisor_view = farm.advisor.client.get(tasks_url(farm, f"/{worker_task['id']}")).json()
    assert advisor_view["allowed_actions"] == ["edit_task"]
    for name in ("complete", "discard"):
        response = farm.advisor.client.post(tasks_url(farm, f"/{worker_task['id']}/{name}"))
        assert response.status_code == 403
        assert response.json()["detail"] == "forbidden_for_role"
    recorded = farm.advisor.client.post(tasks_url(farm), json={"title": "Erledigt", "done": True})
    assert recorded.status_code == 403


def test_delete_is_for_admins_and_creators(farm: Farm) -> None:
    by_worker = create(farm.worker, farm)["id"]
    by_admin = create(farm.admin, farm)["id"]

    denied = farm.worker.client.delete(tasks_url(farm, f"/{by_admin}"))
    assert (denied.status_code, denied.json()["detail"]) == (403, "only_admin_or_creator")

    assert farm.worker.client.delete(tasks_url(farm, f"/{by_worker}")).status_code == 204
    assert farm.admin.client.delete(tasks_url(farm, f"/{by_admin}")).status_code == 204
    assert farm.admin.client.get(tasks_url(farm, f"/{by_admin}")).status_code == 404


def test_list_filters(farm: Farm) -> None:
    today = date.today()
    overdue = create(farm.admin, farm, title="überfällig", due_date=str(today - timedelta(days=2)))
    soon = create(
        farm.admin,
        farm,
        title="bald",
        due_date=str(today + timedelta(days=3)),
        priority="high",
        assignee_id=farm.worker.id,
    )
    later = create(farm.admin, farm, title="später", due_date=str(today + timedelta(days=30)))
    undated = create(farm.admin, farm, title="ohne Datum", assignee_id=farm.admin.id)
    done = create(farm.admin, farm, title="erledigt", done=True)
    discarded = create(farm.admin, farm, title="verworfen")
    farm.admin.client.post(tasks_url(farm, f"/{discarded['id']}/discard"))

    def titles(**params: Any) -> list[str]:
        response = farm.admin.client.get(tasks_url(farm), params=params)
        assert response.status_code == 200, response.text
        return [task["title"] for task in response.json()]

    # Open first, by due date (undated last), then done, then discarded.
    assert titles() == [
        overdue["title"],
        soon["title"],
        later["title"],
        undated["title"],
        done["title"],
        discarded["title"],
    ]
    assert titles(status=["done", "discarded"]) == ["erledigt", "verworfen"]
    assert titles(assignee="me") == ["ohne Datum"]
    assert titles(assignee=farm.worker.id) == ["bald"]
    assert "bald" not in titles(assignee="none")
    assert titles(priority="high") == ["bald"]
    assert titles(status="open", due_before=str(today + timedelta(days=7))) == [
        "überfällig",
        "bald",
    ]
    assert titles(status="open", without_due=True) == ["ohne Datum"]
    assert farm.admin.client.get(tasks_url(farm), params={"assignee": "x"}).status_code == 422


def test_members_list_shows_who_can_be_assigned(farm: Farm) -> None:
    members = farm.advisor.client.get(f"/api/farms/{farm.id}/members").json()

    assert [(m["user"]["email"], m["role"], m["assignable"]) for m in members] == [
        ("anna@example.at", "admin", True),
        ("berta@example.at", "advisor", False),
        ("wolf@example.at", "worker", True),
    ]


def test_tasks_stay_inside_their_farm(farm: Farm) -> None:
    task_id = create(farm.admin, farm)["id"]
    stranger_farm = farm.stranger.client.get("/api/me").json()["memberships"][0]["farm"]["id"]

    assert farm.stranger.client.get(tasks_url(farm)).status_code == 404
    assert farm.stranger.client.get(tasks_url(farm, f"/{task_id}")).status_code == 404
    via_own_farm = farm.stranger.client.post(f"/api/farms/{stranger_farm}/tasks/{task_id}/complete")
    assert (via_own_farm.status_code, via_own_farm.json()["detail"]) == (404, "task_not_found")


def test_work_of_a_deleted_account_stays_on_record(farm: Farm, db: Session) -> None:
    task_id = create(farm.worker, farm, done=True)["id"]

    db.execute(delete(User).where(User.email == "wolf@example.at"))
    db.commit()

    task = farm.admin.client.get(tasks_url(farm, f"/{task_id}")).json()
    assert task["status"] == "done"
    assert (task["created_by"], task["completed_by"]) == (None, None)
    assert task["completed_at"] is not None


def test_tasks_refer_to_fields_and_plots_of_one_harvest_year(farm: Farm, areas: Areas) -> None:
    task = create(
        farm.worker,
        farm,
        field_ids=[areas.field_2027],
        plot_ids=[areas.plot_2027_b, areas.plot_2027_a],
    )

    assert task["harvest_year"] == 2027
    assert [(f["number"], f["name"]) for f in task["fields"]] == [(1, "Feld 1")]
    assert [
        (p["field_number"], p["number"], p["land_use_name"], p["land_use_category"])
        for p in task["plots"]
    ] == [
        (1, 1, "WINTERROGGEN", "cereals"),
        (1, 2, "GRÜNBRACHE", "fallow"),
    ]


def test_harvest_years_cannot_be_mixed_and_areas_stay_on_their_farm(
    farm: Farm, areas: Areas
) -> None:
    mixed = farm.admin.client.post(
        tasks_url(farm),
        json={"title": "Zaun", "field_ids": [areas.field_2026], "plot_ids": [areas.plot_2027_a]},
    )
    foreign = farm.admin.client.post(
        tasks_url(farm), json={"title": "Zaun", "plot_ids": [areas.elsewhere_plot]}
    )

    assert (mixed.status_code, mixed.json()["detail"]) == (422, "mixed_harvest_years")
    assert (foreign.status_code, foreign.json()["detail"]) == (422, "area_not_found")


def test_changing_areas_moves_the_task_between_harvest_years(farm: Farm, areas: Areas) -> None:
    task = create(farm.admin, farm, plot_ids=[areas.plot_2027_a])

    moved = farm.admin.client.patch(
        tasks_url(farm, f"/{task['id']}"), json={"plot_ids": [areas.plot_2026]}
    ).json()
    assert (moved["harvest_year"], [p["land_use_name"] for p in moved["plots"]]) == (
        2026,
        ["SONNENBLUMEN"],
    )

    cleared = farm.admin.client.patch(
        tasks_url(farm, f"/{task['id']}"), json={"plot_ids": None}
    ).json()
    assert (cleared["harvest_year"], cleared["plots"]) == (None, [])


def test_list_by_harvest_year_includes_tasks_without_one(farm: Farm, areas: Areas) -> None:
    create(farm.admin, farm, title="2027", plot_ids=[areas.plot_2027_a])
    create(farm.admin, farm, title="2026", plot_ids=[areas.plot_2026])
    create(farm.admin, farm, title="allgemein")
    create(farm.admin, farm, title="Feldstück 2027", field_ids=[areas.field_2027])

    def titles(**params: Any) -> list[str]:
        return sorted(
            t["title"] for t in farm.admin.client.get(tasks_url(farm), params=params).json()
        )

    assert titles(harvest_year=2027) == ["2027", "Feldstück 2027", "allgemein"]
    assert titles(harvest_year=2026) == ["2026", "allgemein"]
    assert titles(plot_id=areas.plot_2027_a) == ["2027"]
    assert titles() == ["2026", "2027", "Feldstück 2027", "allgemein"]
