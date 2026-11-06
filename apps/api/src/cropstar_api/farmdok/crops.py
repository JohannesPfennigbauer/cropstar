"""farmdok crop names as AMA Land Use codes.

farmdok names crops in its own words ("Winterweichweizen < 14 % Rohprotein", "Sojabohne").
A name maps to an AMA code if `crops.csv` lists it, or if it equals an AMA Land Use name
apart from case and spacing. The table only lists names whose AMA code is unambiguous;
names such as "Sonstige Grünlandfläche", which farmdok uses for hedges and field margins
alike, are left for the Admin to assign.
"""

import csv
from functools import cache
from importlib.resources import files

from cropstar_api.land_use import land_use_names

# farmdok's Field land use, as AMA names Field land uses (FNAR) in the eAMA export.
_FIELD_LAND_USES = {"ackerland": ("A", "ACKERLAND")}


def land_use(crop: str) -> tuple[str, str] | None:
    """The AMA code and name for a farmdok crop name, if it is known."""
    key = _normalise(crop)
    code = _table().get(key) or _ama_by_name().get(key)
    return (code, land_use_names()[code]) if code else None


def field_land_use(name: str | None) -> tuple[str, str]:
    """Field land uses other than arable land are kept as farmdok names them, without code."""
    if not name:
        return ("", "")
    return _FIELD_LAND_USES.get(_normalise(name), ("", name.upper()))


def _normalise(name: str) -> str:
    # AMA writes "WICKEN - GETREIDE GEMENGE", farmdok "Wicken-Getreide Gemenge".
    return " ".join(name.replace(" - ", "-").split()).casefold()


@cache
def _table() -> dict[str, str]:
    text = (files("cropstar_api.farmdok") / "crops.csv").read_text("utf-8")
    rows = csv.DictReader(line for line in text.splitlines() if not line.startswith("#"))
    return {_normalise(row["farmdok_name"]): row["ama_code"] for row in rows}


@cache
def _ama_by_name() -> dict[str, str]:
    return {_normalise(name): code for code, name in land_use_names().items()}
