"""Shared fixtures: a Farm with Admin, Worker, Advisor and a stranger, plus some areas."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cropstar_api.app import create_app
from cropstar_api.auth.provider import PasswordAuthProvider
from cropstar_api.models import Field, Membership, Plot, Role
from cropstar_api.settings import Settings

PASSWORD = "correct horse"


@dataclass
class Person:
    client: TestClient
    id: str
    email: str


@dataclass
class Farm:
    id: str
    admin: Person
    worker: Person
    advisor: Person
    stranger: Person


def sign_in(app_settings: Settings, email: str) -> TestClient:
    client = TestClient(create_app(app_settings))
    response = client.post("/api/auth/sign-in", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def farm(settings: Settings, db: Session) -> Iterator[Farm]:
    """Admin Anna's Farm with Worker Wolf and Advisor Berta, plus Stefan from another Farm."""
    clients: list[TestClient] = []

    def register(email: str, farm_name: str) -> tuple[Person, str]:
        client = TestClient(create_app(settings))
        clients.append(client)
        me = client.post(
            "/api/auth/register",
            json={"email": email, "password": PASSWORD, "farm_name": farm_name},
        ).json()
        return Person(client, me["user"]["id"], email), me["memberships"][0]["farm"]["id"]

    admin, farm_id = register("anna@example.at", "Hof Gruber")
    stranger, _ = register("stefan@example.at", "Hof Huber")

    auth = PasswordAuthProvider(timedelta(days=1))
    people = {}
    for email, role in (("wolf@example.at", Role.WORKER), ("berta@example.at", Role.ADVISOR)):
        identity = auth.register(db, email, PASSWORD)
        db.add(Membership(farm_id=farm_id, user_id=identity.user_id, role=role))
        db.commit()
        client = sign_in(settings, email)
        clients.append(client)
        people[role] = Person(client, str(identity.user_id), email)

    yield Farm(farm_id, admin, people[Role.WORKER], people[Role.ADVISOR], stranger)
    for client in clients:
        client.close()


def tasks_url(farm: Farm, suffix: str = "") -> str:
    return f"/api/farms/{farm.id}/tasks{suffix}"


def create(person: Person, farm: Farm, **body: Any) -> Any:
    response = person.client.post(tasks_url(farm), json={"title": "Zaun reparieren", **body})
    assert response.status_code == 201, response.text
    return response.json()


# ── Fields and Plots ────────────────────────────────────────────────────────


@dataclass
class Areas:
    field_2027: str
    plot_2027_a: str
    plot_2027_b: str
    field_2026: str
    plot_2026: str
    elsewhere_plot: str


def _square(x: float, y: float) -> str:
    """A 100 m square in the AMA CRS, as EWKT."""
    ring = f"{x} {y}, {x + 100} {y}, {x + 100} {y + 100}, {x} {y + 100}, {x} {y}"
    return f"SRID=31287;MULTIPOLYGON((({ring})))"


@pytest.fixture
def areas(farm: Farm, db: Session) -> Areas:
    stranger_farm = farm.stranger.client.get("/api/me").json()["memberships"][0]["farm"]["id"]

    def field(farm_id: str, year: int, number: int) -> Field:
        created = Field(
            farm_id=farm_id,
            harvest_year=year,
            number=number,
            name=f"Feld {number}",
            land_use_code="A",
            land_use_name="ACKERLAND",
            declared_area_ha=1,
            geometry=_square(600_000 + number * 200, 500_000 + year),
        )
        db.add(created)
        db.flush()
        return created

    def plot(parent: Field, number: int, code: str, name: str) -> Plot:
        created = Plot(
            field_id=parent.id,
            number=number,
            land_use_code=code,
            land_use_name=name,
            declared_area_ha=0.5,
            geometry=parent.geometry,
        )
        db.add(created)
        db.flush()
        return created

    f2027 = field(farm.id, 2027, 1)
    f2026 = field(farm.id, 2026, 1)
    result = Areas(
        field_2027=str(f2027.id),
        plot_2027_a=str(plot(f2027, 1, "142", "WINTERROGGEN").id),
        plot_2027_b=str(plot(f2027, 2, "771", "GRÜNBRACHE").id),
        field_2026=str(f2026.id),
        plot_2026=str(plot(f2026, 1, "307", "SONNENBLUMEN").id),
        elsewhere_plot=str(plot(field(stranger_farm, 2027, 9), 1, "142", "WINTERROGGEN").id),
    )
    db.commit()
    return result
