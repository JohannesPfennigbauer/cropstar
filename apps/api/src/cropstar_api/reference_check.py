"""Checking a Farm in Cropstar against the reports it was migrated from.

The reference files are the Farm's eAMA exports, farmdok field lists and farmdok crop
production logs. For every Harvest Year this compares what Cropstar holds with them:

- a year with an eAMA export: the same Fields and Plots, the same Declared Area per Plot,
  geometry from the export;
- a year with only a farmdok field list: the same Plots and areas, geometry provisional and
  about as large as the Plot (borrowed by a wrong number, it would not be);
- every crop production log entry: a Done Task imported from it, on the same date, on
  Plots of the entry's Fields; entries without one are listed, to be explained.

Pure: parsed reports and the Farm's areas and Tasks (as the HTTP API returns them) in,
a list of findings out.
"""

import enum
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import shapely
from shapely.geometry import shape

from cropstar_api.eama import AreaDeclaration
from cropstar_api.farmdok.crop_log import CropLog
from cropstar_api.farmdok.field_list import FieldList

_HA = Decimal("0.0001")
# Borrowed geometry this much larger or smaller than the Plot is probably someone else's.
GEOMETRY_TOLERANCE = 0.2


class Severity(enum.StrEnum):
    OK = "ok"
    # Needs a decision: a deliberate skip, or something to fix.
    CHECK = "check"
    MISMATCH = "mismatch"


@dataclass(frozen=True)
class Finding:
    harvest_year: int
    severity: Severity
    message: str


@dataclass(frozen=True)
class YearState:
    """A Harvest Year in Cropstar, as `GET /plots` and `GET /tasks` return it."""

    plots: Sequence[dict[str, Any]]
    tasks: Sequence[dict[str, Any]]


def check_eama(declaration: AreaDeclaration, state: YearState) -> list[Finding]:
    year = declaration.harvest_year
    declared = {(p.field_number, p.number): p.declared_area_ha for p in declaration.plots}
    held = _plots(state)
    findings = _compare_plots(year, declared, held, "im eAMA-Export")
    not_eama = sorted(k for k, p in held.items() if p["provenance"]["source"] != "eama_export")
    if not_eama:
        findings.append(
            Finding(year, Severity.MISMATCH, f"Geometrie nicht aus eAMA: {_keys(not_eama)}")
        )
    else:
        findings.append(Finding(year, Severity.OK, "Geometrie aller Schläge aus dem eAMA-Export"))
    return findings


def check_field_list(field_list: FieldList, state: YearState) -> list[Finding]:
    year = field_list.harvest_year
    declared = {(r.field_number, r.plot_number): r.plot_area_ha for r in field_list.rows}
    held = _plots(state)
    findings = _compare_plots(year, declared, held, "in der farmdok-Feldstücksliste")
    sources: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for key, plot in held.items():
        sources[plot["provenance"]["source"]].append(key)
    if sources.get("eama_export"):
        findings.append(
            Finding(year, Severity.CHECK, "Geometrie aus einem eAMA-Export statt vorläufig")
        )
    borrowed = len(sources.get("borrowed", []))
    if borrowed:
        years = {
            p["provenance"]["borrowed_from_year"]
            for p in held.values()
            if p["provenance"]["source"] == "borrowed"
        }
        origin = ", ".join(str(y) for y in sorted(years))
        findings.append(
            Finding(year, Severity.OK, f"{borrowed} Schläge mit vorläufiger Geometrie aus {origin}")
        )
    misfits = []
    for key in sorted(sources.get("borrowed", [])):
        plot = held[key]
        if plot.get("geometry") is None:
            continue
        size = _area_ha(plot["geometry"])
        area = float(plot["declared_area_ha"])
        if area > 0 and abs(size - area) > GEOMETRY_TOLERANCE * area:
            misfits.append(f"{key[0]}.{key[1]} ({area:.2f} ha, Geometrie {size:.2f} ha)")
    if misfits:
        findings.append(
            Finding(
                year,
                Severity.CHECK,
                f"Vorläufige Geometrie passt in der Größe nicht: {', '.join(misfits)}",
            )
        )
    if sources.get("none"):
        findings.append(
            Finding(
                year,
                Severity.CHECK,
                f"Ohne Geometrie (nichts zu übernehmen): {_keys(sorted(sources['none']))}",
            )
        )
    return findings


def check_crop_log(log: CropLog, state: YearState) -> list[Finding]:
    year = log.harvest_year
    imported = [
        t for t in state.tasks if (t.get("imported") or {}).get("kind") == "farmdok_crop_log"
    ]
    if not imported:
        return [Finding(year, Severity.MISMATCH, "Pflanzenbaujournal nicht importiert")]
    available = list(imported)
    missing = []
    for entry in log.entries:
        match = next(
            (
                t
                for t in available
                if _matches(t, entry.activity, entry.performed_on, entry.field_numbers)
            ),
            None,
        )
        if match is None:
            missing.append(entry)
        else:
            available.remove(match)
    findings = [
        Finding(
            year,
            Severity.OK if not missing else Severity.CHECK,
            f"{len(log.entries) - len(missing)} von {len(log.entries)} Journaleinträgen als "
            "erledigte Aufgaben importiert",
        )
    ]
    for entry in missing:
        fields = ", ".join(str(n) for n in entry.field_numbers)
        findings.append(
            Finding(
                year,
                Severity.CHECK,
                f"Nicht importiert (übersprungen?): Zeile {entry.row}, "
                f"{entry.performed_on:%d.%m.%Y} {entry.activity}, Feldstück {fields}, {entry.crop}",
            )
        )
    if available:
        findings.append(
            Finding(
                year,
                Severity.MISMATCH,
                f"{len(available)} importierte Aufgaben ohne passenden Journaleintrag",
            )
        )
    return findings


def _matches(
    task: dict[str, Any], activity: str, performed_on: date, fields: tuple[int, ...]
) -> bool:
    operations = task.get("operations") or []
    return (
        task["title"] == activity[:200]
        and bool(operations)
        and all(o["performed_on"] == performed_on.isoformat() for o in operations)
        and all(o["plot"]["field_number"] in fields for o in operations)
    )


def _plots(state: YearState) -> dict[tuple[int, int], dict[str, Any]]:
    return {(p["field"]["number"], p["number"]): p for p in state.plots}


def _area_ha(geojson: dict[str, Any]) -> float:
    """Roughly, from WGS84: within a fraction of a percent for a farm's Plots."""
    geometry = shape(geojson)
    scale = np.array([111_320 * math.cos(math.radians(geometry.centroid.y)), 110_574])
    return float(shapely.transform(geometry, lambda xy: xy * scale).area) / 10_000


def _compare_plots(
    year: int,
    declared: dict[tuple[int, int], Decimal],
    held: dict[tuple[int, int], dict[str, Any]],
    source: str,
) -> list[Finding]:
    """`source` says where the reference is, e.g. "im eAMA-Export"."""
    findings = []
    only_declared = sorted(declared.keys() - held.keys())
    only_held = sorted(held.keys() - declared.keys())
    if only_declared:
        findings.append(
            Finding(
                year,
                Severity.MISMATCH,
                f"{source[0].upper()}{source[1:]}, nicht in Cropstar: {_keys(only_declared)}",
            )
        )
    if only_held:
        findings.append(
            Finding(year, Severity.MISMATCH, f"In Cropstar, nicht {source}: {_keys(only_held)}")
        )
    areas = {k: Decimal(str(held[k]["declared_area_ha"])).quantize(_HA) for k in held}
    area_differences = [
        f"{k[0]}.{k[1]} ({declared[k]} statt {areas[k]} ha)"
        for k in sorted(declared.keys() & held.keys())
        if areas[k] != declared[k].quantize(_HA)
    ]
    if area_differences:
        findings.append(
            Finding(year, Severity.MISMATCH, f"Fläche weicht ab: {', '.join(area_differences)}")
        )
    if not (only_declared or only_held or area_differences):
        total = sum(declared.values(), Decimal(0))
        findings.append(
            Finding(
                year,
                Severity.OK,
                f"{len(declared)} Schläge, {total.quantize(_HA)} ha, wie {source}",
            )
        )
    return findings


def _keys(keys: Sequence[tuple[int, int]]) -> str:
    return ", ".join(f"{field}.{plot}" for field, plot in keys)
