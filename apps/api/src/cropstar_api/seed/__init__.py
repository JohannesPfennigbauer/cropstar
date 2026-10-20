"""Demo data for development: a Farm with real Fields and Plots from public INVEKOS data."""

import json
from importlib.resources import files
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cropstar_api.auth.provider import PasswordAuthProvider, normalize_email
from cropstar_api.models import AMA_SRID, Farm, Field, Membership, Plot, Role, User

DEMO_FARM_NAME = "Demo-Betrieb Weinviertel"
DEMO_HARVEST_YEAR = 2026


def load_fixture() -> dict[str, Any]:
    text = (files("cropstar_api.seed") / "invekos_demo_2026.geojson").read_text("utf-8")
    fixture: dict[str, Any] = json.loads(text)
    return fixture


def seed_demo(db: Session, auth: PasswordAuthProvider, email: str, password: str) -> Farm:
    """Make `email` Admin of the demo Farm, creating the user and the Farm as needed.
    Re-running replaces the demo Fields and Plots instead of duplicating them."""
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        identity = auth.register(db, email, password)
        user_id = identity.user_id
    else:
        user_id = user.id

    farm = db.scalar(
        select(Farm)
        .join(Membership)
        .where(Membership.user_id == user_id, Farm.name == DEMO_FARM_NAME)
    )
    if farm is None:
        farm = Farm(name=DEMO_FARM_NAME)
        db.add(farm)
        db.flush()
        db.add(Membership(farm_id=farm.id, user_id=user_id, role=Role.ADMIN))
    for field in db.scalars(select(Field).where(Field.farm_id == farm.id)):
        db.delete(field)
    db.flush()

    features = load_fixture()["features"]
    fields: dict[int, Field] = {}
    for feature in (f for f in features if f["properties"]["kind"] == "field"):
        p = feature["properties"]
        field = Field(
            farm_id=farm.id,
            harvest_year=DEMO_HARVEST_YEAR,
            number=p["number"],
            name=p["name"],
            land_use_code=p["fnar_code"],
            land_use_name=p["fnar_bezeichnung"],
            declared_area_ha=p["fs_flaeche_ha"],
            geometry=_ama_geometry(feature["geometry"]),
        )
        db.add(field)
        fields[p["fs_kennung"]] = field
    db.flush()
    for feature in (f for f in features if f["properties"]["kind"] == "plot"):
        p = feature["properties"]
        db.add(
            Plot(
                field_id=fields[p["fs_kennung"]].id,
                number=p["number"],
                land_use_code=p["snar_code"],
                land_use_name=p["snar_bezeichnung"],
                declared_area_ha=p["sl_flaeche_brutto_ha"],
                geometry=_ama_geometry(feature["geometry"]),
            )
        )
    db.flush()
    return farm


def _ama_geometry(geometry: dict[str, Any]) -> Any:
    return func.ST_Multi(func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)), AMA_SRID))
