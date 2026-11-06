from typing import Any

import pytest

from tests.farm_fixtures import Areas, Farm, Person, create

SLURRY = {
    "kind": "fertiliser",
    "name": "Rindergülle",
    "unit": "m3",
    "dry_matter_percent": 7.5,
    "total_n": 4.2,
    "available_n": 2.4,
    "p2o5": 1.6,
    "k2o": 5.5,
    "value_source": "lab_analysis",
    "source_reference": "Labor Musterstadt, Probe 42",
    "analysed_on": "2026-03-02",
}
WHEAT = {
    "kind": "seed",
    "name": "Winterweizen Z-Saatgut",
    "land_use_code": "138",
    "variety": "Capo",
    "thousand_kernel_weight_g": 46,
}


def url(farm: Farm, suffix: str = "") -> str:
    return f"/api/farms/{farm.id}/farm-inputs{suffix}"


def add(person: Person, farm: Farm, body: dict[str, Any]) -> Any:
    response = person.client.post(url(farm), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_admins_and_workers_keep_the_farm_inputs(farm: Farm) -> None:
    slurry = add(farm.worker, farm, SLURRY)
    wheat = add(farm.admin, farm, WHEAT)

    assert (slurry["total_n"], slurry["value_source"], slurry["in_use"]) == (
        4.2,
        "lab_analysis",
        False,
    )
    assert (wheat["land_use_name"], wheat["unit"]) == ("WINTERWEICHWEIZEN", None)
    listed = farm.advisor.client.get(url(farm)).json()
    assert [i["name"] for i in listed] == ["Rindergülle", "Winterweizen Z-Saatgut"]
    seeds = farm.advisor.client.get(url(farm), params={"kind": "seed"}).json()
    assert [i["id"] for i in seeds] == [wheat["id"]]


def test_a_new_lab_analysis_replaces_the_values(farm: Farm) -> None:
    slurry = add(farm.worker, farm, SLURRY)

    updated = farm.worker.client.put(
        url(farm, f"/{slurry['id']}"),
        json={k: v for k, v in SLURRY.items() if k != "kind"}
        | {"total_n": 3.9, "analysed_on": "2026-10-20"},
    )

    assert updated.status_code == 200, updated.text
    assert (updated.json()["total_n"], updated.json()["analysed_on"]) == (3.9, "2026-10-20")


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        (SLURRY | {"value_source": None}, "value_source_required"),
        (SLURRY | {"unit": None}, "unit_required"),
        (WHEAT | {"land_use_code": None}, "land_use_required"),
        (WHEAT | {"total_n": 3}, "fertiliser_fields_not_allowed"),
        ({"kind": "other", "name": "Netzmittel", "variety": "x"}, "seed_fields_not_allowed"),
    ],
)
def test_incomplete_or_mixed_inputs_are_refused(
    farm: Farm, body: dict[str, Any], detail: str
) -> None:
    response = farm.admin.client.post(url(farm), json=body)

    assert (response.status_code, response.json()["detail"]) == (422, detail)


@pytest.mark.parametrize(
    "change",
    [
        {"available_n": 5.0},
        {"dry_matter_percent": 101},
        {"p2o5": -1},
        {"analysed_on": None},
        {"catalogue_entry": "no-such-entry"},
    ],
    ids=[
        "available above total",
        "dry matter above 100",
        "negative",
        "lab without date",
        "unknown catalogue entry",
    ],
)
def test_implausible_values_are_refused(farm: Farm, change: dict[str, Any]) -> None:
    response = farm.admin.client.post(url(farm), json=SLURRY | change)

    assert response.status_code == 422


def test_unknown_land_uses_are_refused(farm: Farm) -> None:
    response = farm.admin.client.post(url(farm), json=WHEAT | {"land_use_code": "999999"})

    assert response.status_code == 422


def test_advisors_read_but_do_not_write(farm: Farm) -> None:
    slurry = add(farm.admin, farm, SLURRY)
    client = farm.advisor.client

    refused = [
        client.post(url(farm), json=SLURRY),
        client.put(url(farm, f"/{slurry['id']}"), json={"name": "Gülle"}),
        client.post(url(farm, f"/{slurry['id']}/archive")),
        client.delete(url(farm, f"/{slurry['id']}")),
    ]

    assert [(r.status_code, r.json()["detail"]) for r in refused] == [
        (403, "forbidden_for_role")
    ] * 4
    assert client.get(url(farm, f"/{slurry['id']}")).status_code == 200


def test_inputs_stay_inside_their_farm(farm: Farm) -> None:
    slurry = add(farm.admin, farm, SLURRY)

    assert farm.stranger.client.get(url(farm)).status_code == 404
    stranger_farm = farm.stranger.client.get("/api/me").json()["memberships"][0]["farm"]["id"]
    elsewhere = farm.stranger.client.get(f"/api/farms/{stranger_farm}/farm-inputs/{slurry['id']}")
    assert elsewhere.status_code == 404


def test_archived_inputs_are_hidden_from_current_ones_and_can_return(farm: Farm) -> None:
    slurry = add(farm.admin, farm, SLURRY)

    archived = farm.worker.client.post(url(farm, f"/{slurry['id']}/archive")).json()
    current = farm.worker.client.get(url(farm), params={"archived": False}).json()
    restored = farm.worker.client.post(url(farm, f"/{slurry['id']}/restore")).json()

    assert archived["archived_at"] is not None
    assert current == []
    assert restored["archived_at"] is None


def test_unused_inputs_are_deleted(farm: Farm) -> None:
    slurry = add(farm.admin, farm, SLURRY)

    response = farm.worker.client.delete(url(farm, f"/{slurry['id']}"))

    assert response.status_code == 204
    assert farm.admin.client.get(url(farm)).json() == []


def test_inputs_that_records_refer_to_are_archived_not_deleted(farm: Farm, areas: Areas) -> None:
    slurry = add(farm.admin, farm, SLURRY)
    create(
        farm.worker,
        farm,
        title="Gülle",
        operation_type="fertilisation",
        plot_ids=[areas.plot_2027_a],
        planned_details={"type": "fertilisation", "farm_input_id": slurry["id"]},
    )

    refused = farm.admin.client.delete(url(farm, f"/{slurry['id']}"))
    listed = farm.admin.client.get(url(farm)).json()
    archived = farm.admin.client.post(url(farm, f"/{slurry['id']}/archive"))

    assert (refused.status_code, refused.json()["detail"]) == (409, "farm_input_in_use")
    assert listed[0]["in_use"] is True
    assert archived.status_code == 200


def test_the_catalogue_names_its_source(farm: Farm) -> None:
    entries = farm.advisor.client.get(f"/api/farms/{farm.id}/farm-input-catalogue").json()

    assert entries
    assert all(e["source"] for e in entries)


def test_starting_from_the_catalogue_copies_its_values(farm: Farm) -> None:
    entry = farm.admin.client.get(f"/api/farms/{farm.id}/farm-input-catalogue").json()[0]
    copied = {
        key: entry[key]
        for key in ("unit", "dry_matter_percent", "total_n", "available_n", "p2o5", "k2o")
    }

    created = add(
        farm.admin,
        farm,
        {
            "kind": "fertiliser",
            "name": entry["name"],
            "value_source": "standard_value",
            "source_reference": entry["source"],
            "catalogue_entry": entry["code"],
        }
        | copied,
    )
    edited = farm.admin.client.put(
        url(farm, f"/{created['id']}"),
        json={
            k: v
            for k, v in created.items()
            if k in SLURRY or k in ("source_reference", "catalogue_entry")
        }
        | {"total_n": 99},
    )

    assert {key: created[key] for key in copied} == copied
    assert created["catalogue_entry"] == entry["code"]
    assert edited.status_code == 200, edited.text
    unchanged = farm.admin.client.get(f"/api/farms/{farm.id}/farm-input-catalogue").json()[0]
    assert unchanged == entry


def test_land_uses_are_offered_for_seed(farm: Farm) -> None:
    land_uses = farm.worker.client.get(f"/api/farms/{farm.id}/land-uses").json()

    assert {"code": "138", "name": "WINTERWEICHWEIZEN"} in land_uses
