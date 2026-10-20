from typing import Any

from tests.farm_fixtures import Areas, Farm, Person, create, tasks_url


def years_url(farm: Farm, suffix: str = "") -> str:
    return f"/api/farms/{farm.id}/harvest-years{suffix}"


def lock(person: Person, farm: Farm, year: int) -> Any:
    return person.client.put(years_url(farm, f"/{year}/lock"))


def years(person: Person, farm: Farm) -> dict[int, Any]:
    response = person.client.get(years_url(farm))
    assert response.status_code == 200, response.text
    return {entry["year"]: entry["lock"] for entry in response.json()}


def test_only_admins_lock_and_unlock_and_everyone_sees_who_did(farm: Farm, areas: Areas) -> None:
    for person in (farm.worker, farm.advisor):
        denied = lock(person, farm, 2027)
        assert (denied.status_code, denied.json()["detail"]) == (403, "forbidden_for_role")

    locked = lock(farm.admin, farm, 2027)
    assert locked.status_code == 200, locked.text
    assert locked.json()["lock"]["locked_by"]["email"] == farm.admin.email

    seen = years(farm.advisor, farm)
    assert seen[2026] is None
    assert seen[2027]["locked_by"]["email"] == farm.admin.email
    assert seen[2027]["locked_at"] == locked.json()["lock"]["locked_at"]

    # Locking again keeps the original lock.
    assert lock(farm.admin, farm, 2027).json()["lock"] == locked.json()["lock"]

    denied = farm.worker.client.delete(years_url(farm, "/2027/lock"))
    assert denied.status_code == 403
    unlocked = farm.admin.client.delete(years_url(farm, "/2027/lock"))
    assert (unlocked.status_code, unlocked.json()["lock"]) == (200, None)
    assert years(farm.worker, farm)[2027] is None


def test_only_years_with_fields_can_be_locked(farm: Farm, areas: Areas) -> None:
    response = lock(farm.admin, farm, 2030)

    assert (response.status_code, response.json()["detail"]) == (404, "harvest_year_not_found")


def test_a_locked_year_refuses_every_write(farm: Farm, areas: Areas) -> None:
    plots = [areas.plot_2027_a, areas.plot_2027_b]
    task = create(farm.worker, farm, title="Striegeln", operation_type="tillage", plot_ids=plots)
    soil = create(farm.worker, farm, title="Bodenprobe", plot_ids=[areas.plot_2026])
    lock(farm.admin, farm, 2027)
    url = tasks_url(farm, f"/{task['id']}")
    op = f"{url}/operations/{task['operations'][0]['id']}"
    client = farm.admin.client

    refused = [
        client.patch(url, json={"title": "Später"}),
        client.patch(url, json={"plot_ids": [areas.plot_2027_a]}),
        client.post(f"{url}/complete"),
        client.post(f"{url}/discard"),
        client.delete(url),
        client.post(f"{op}/complete", json={}),
        client.patch(op, json={"actual_details": "Striegel, 3 cm"}),
        client.post(tasks_url(farm), json={"title": "Neu", "plot_ids": [areas.plot_2027_a]}),
        client.patch(tasks_url(farm, f"/{soil['id']}"), json={"plot_ids": [areas.plot_2027_a]}),
    ]
    assert [(r.status_code, r.json()["detail"]) for r in refused] == [
        (403, "harvest_year_locked")
    ] * len(refused)

    read = client.get(url).json()
    assert (read["title"], read["status"], read["allowed_actions"]) == ("Striegeln", "open", [])
    assert all(o["allowed_actions"] == [] for o in read["operations"])


def test_tasks_without_areas_or_in_other_years_stay_editable(farm: Farm, areas: Areas) -> None:
    general = create(farm.worker, farm, title="Traktor-Service")
    soil = create(farm.worker, farm, title="Bodenprobe", plot_ids=[areas.plot_2026])
    lock(farm.admin, farm, 2027)

    for task in (general, soil):
        url = tasks_url(farm, f"/{task['id']}")
        assert farm.worker.client.patch(url, json={"title": "Erledigt"}).status_code == 200
        assert farm.worker.client.post(f"{url}/complete").status_code == 200
    create(farm.worker, farm, title="Hecke schneiden")
