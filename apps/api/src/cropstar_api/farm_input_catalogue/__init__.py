"""A read-only catalogue of standard nutrient contents for farm manure.

The Austrian guidelines (_Richtlinien für die sachgerechte Düngung_, RSD, 8th edition) give
nutrients per animal place and year, not per m³. Following their own method (p. 123,
worked example in Tab. 81), contents per m³ are the yearly nutrients of a place divided by
the manure volume it produces in a year:

- total N = N ab Lager (Tab. 64) / (2 * volume per 6 months, Tab. 71)
- plant-available N = total N * (1 - spreading loss, Tab. 63) * availability (Tab. 67)
- P2O5, K2O = Tab. 70 / the same volume; Tab. 70 does not split them between solid manure
  and liquid manure (Jauche), so those entries have none.

The inputs are kept as printed in `rsd_8.csv`. Volumes are undiluted; the RSD itself says the
farm's real volumes or a lab analysis are better. New Farm Inputs copy an entry; the copy
never changes when the catalogue does.
"""

import csv
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from importlib.resources import files

from cropstar_api.models import FarmInputUnit

EDITION = "RSD, 8. Auflage (aktualisierte Version 2023), BMLUK"
_CENT = Decimal("0.01")


@dataclass(frozen=True)
class CatalogueEntry:
    code: str
    name: str
    unit: FarmInputUnit
    dry_matter_percent: Decimal | None
    total_n: Decimal | None
    available_n: Decimal | None
    p2o5: Decimal | None
    k2o: Decimal | None
    # The publication, its edition and how the values follow from its tables.
    source: str


@cache
def catalogue() -> tuple[CatalogueEntry, ...]:
    text = (files("cropstar_api.farm_input_catalogue") / "rsd_8.csv").read_text("utf-8")
    rows = csv.DictReader(line for line in text.splitlines() if not line.startswith("#"))
    return tuple(_derive(row) for row in rows)


def entry(code: str) -> CatalogueEntry | None:
    return next((e for e in catalogue() if e.code == code), None)


def _derive(row: dict[str, str]) -> CatalogueEntry:
    volume = 2 * Decimal(row["volume_6m"])
    herd = Decimal(row["herd_factor"])

    def per_m3(value: str) -> Decimal | None:
        return _round(Decimal(value) * herd / volume) if value.strip() else None

    total_n = Decimal(row["nal"]) * herd / volume
    available_n = total_n * (1 - Decimal(row["spreading_loss"])) * Decimal(row["availability"])
    tables = "Tab. 64, 63, 67, 70, 71" if row["p2o5"].strip() else "Tab. 64, 63, 67, 71"
    return CatalogueEntry(
        code=row["code"],
        name=row["name"],
        unit=FarmInputUnit.CUBIC_METRE,
        dry_matter_percent=None,
        total_n=_round(total_n),
        available_n=_round(available_n),
        p2o5=per_m3(row["p2o5"]),
        k2o=per_m3(row["k2o"]),
        source=(
            f"{EDITION}: abgeleitet aus {tables} für „{row['animal']}“, {row['system']}, "
            "unverdünnt; Berechnung wie Tab. 81"
        ),
    )


def _round(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)
