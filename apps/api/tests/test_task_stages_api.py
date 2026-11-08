from typing import Any

from tests.farm_fixtures import Farm, create, tasks_url


def stages_url(farm: Farm) -> str:
    return f"/api/farms/{farm.id}/task-stages"


def stages(farm: Farm) -> list[dict[str, Any]]:
    response: list[dict[str, Any]] = farm.worker.client.get(stages_url(farm)).json()
    return response


def test_a_new_farm_has_the_default_stages_and_tasks_start_in_the_first(farm: Farm) -> None:
    planned, open_, doing = stages(farm)

    task = create(farm.worker, farm, title="Zaun")

    assert [s["name"] for s in (planned, open_, doing)] == ["Geplant", "Offen", "In Arbeit"]
    assert task["stage_id"] == planned["id"]


def test_tasks_move_between_stages(farm: Farm) -> None:
    doing = stages(farm)[2]
    task = create(farm.worker, farm, title="Zaun")

    moved = farm.advisor.client.patch(
        tasks_url(farm, f"/{task['id']}"), json={"stage_id": doing["id"]}
    )
    cleared = farm.worker.client.patch(tasks_url(farm, f"/{task['id']}"), json={"stage_id": None})

    assert moved.json()["stage_id"] == doing["id"]
    assert cleared.status_code == 422


def test_a_stage_of_another_farm_is_refused(farm: Farm) -> None:
    stranger_farm = farm.stranger.client.get("/api/me").json()["memberships"][0]["farm"]["id"]
    foreign = farm.stranger.client.get(f"/api/farms/{stranger_farm}/task-stages").json()[0]

    response = farm.worker.client.post(
        tasks_url(farm), json={"title": "Zaun", "stage_id": foreign["id"]}
    )

    assert (response.status_code, response.json()["detail"]) == (422, "stage_not_found")


def test_admins_rename_reorder_add_and_remove_stages(farm: Farm) -> None:
    planned, open_, doing = stages(farm)
    task = create(farm.worker, farm, title="Zaun", stage_id=doing["id"])

    response = farm.admin.client.put(
        stages_url(farm),
        json={
            "stages": [
                {"id": open_["id"], "name": "Bereit"},
                {"id": planned["id"], "name": "Geplant"},
                {"name": "Warten auf Wetter"},
            ]
        },
    )

    assert response.status_code == 200, response.text
    assert [s["name"] for s in response.json()] == ["Bereit", "Geplant", "Warten auf Wetter"]
    # The removed stage's Task moved to the first one.
    moved = farm.admin.client.get(tasks_url(farm, f"/{task['id']}")).json()
    assert moved["stage_id"] == open_["id"]
    assert response.json()[0]["task_count"] == 1


def test_stage_lists_are_checked(farm: Farm) -> None:
    def put(body: Any) -> Any:
        return farm.admin.client.put(stages_url(farm), json=body)

    assert put({"stages": []}).status_code == 422
    assert (
        put({"stages": [{"name": "A"}, {"name": "a"}]}).json()["detail"] == "duplicate_stage_name"
    )
    stranger_farm = farm.stranger.client.get("/api/me").json()["memberships"][0]["farm"]["id"]
    foreign = farm.stranger.client.get(f"/api/farms/{stranger_farm}/task-stages").json()[0]
    assert (
        put({"stages": [{"id": foreign["id"], "name": "X"}]}).json()["detail"] == "stage_not_found"
    )


def test_only_admins_change_the_stages(farm: Farm) -> None:
    response = farm.worker.client.put(stages_url(farm), json={"stages": [{"name": "Alles"}]})

    assert (response.status_code, response.json()["detail"]) == (403, "forbidden_for_role")
