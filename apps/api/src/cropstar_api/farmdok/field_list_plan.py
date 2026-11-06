"""Planning a farmdok field list import: Fields and Plots with borrowed geometry.

A Harvest Year without eAMA export borrows geometry from another year's areas: a Plot takes
the Plot with the same Field and Plot number if its area fits, else the one Plot of the same
Field whose area fits (eAMA renumbers Plots that farmdok keeps), else its Field's geometry,
else none. Fields
take the Field with the same number, else none. All of it is provisional. Crop names become
AMA Land Use codes through `crops`, or through the Admin's assignments for names it does
not know.

Pure and generic in the geometry type, so preview and apply run the same code.
"""

import enum
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from cropstar_api.farmdok import crops
from cropstar_api.farmdok.field_list import FieldList
from cropstar_api.land_use import land_use_names

# A number match is trusted when the areas are this close; farmdok areas are often rounded.
NUMBER_TOLERANCE = Decimal("0.10")
# A Plot found by area alone must be much closer, and the only one that close.
AREA_TOLERANCE = Decimal("0.02")
# Tiny Plots (margins, corners) differ by a few m² between farmdok and eAMA.
MIN_TOLERANCE_HA = Decimal("0.005")


class GeometryMatch(enum.StrEnum):
    # The reference year's Plot with the same Field and Plot number.
    PLOT = "plot"
    # The one reference Plot of the same Field with (almost) the same area, renumbered.
    AREA = "area"
    # The reference year's Field with the same number; for a Plot, the whole Field.
    FIELD = "field"
    NONE = "none"


class InvalidCropAssignmentError(ValueError):
    """An assignment names a crop the list does not contain, or an unknown Land Use."""


@dataclass(frozen=True)
class Reference[G]:
    """The areas of the year to borrow from, by number."""

    harvest_year: int
    fields: Mapping[int, G]
    plots: Mapping[tuple[int, int], G]
    # Declared Area per Plot; without it, numbers are trusted as they are.
    plot_areas: Mapping[tuple[int, int], Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class PlannedField[G]:
    number: int
    name: str | None
    land_use_code: str
    land_use_name: str
    declared_area_ha: Decimal
    geometry: G | None
    match: GeometryMatch


@dataclass(frozen=True)
class PlannedPlot[G]:
    field_number: int
    number: int
    crop: str
    # None while the crop is unknown.
    land_use: tuple[str, str] | None
    declared_area_ha: Decimal
    geometry: G | None
    match: GeometryMatch


@dataclass(frozen=True)
class UnknownCrop:
    name: str
    plot_count: int


@dataclass(frozen=True)
class FieldListPlan[G]:
    harvest_year: int
    reference_year: int | None
    fields: tuple[PlannedField[G], ...]
    plots: tuple[PlannedPlot[G], ...]
    # Crops neither the mapping nor the Admin has assigned yet.
    unknown_crops: tuple[UnknownCrop, ...]


def plan[G](
    field_list: FieldList,
    reference: Reference[G] | None,
    crop_assignments: Mapping[str, str],
) -> FieldListPlan[G]:
    """`crop_assignments` maps farmdok crop names to AMA Land Use codes."""
    crop_names = {row.crop for row in field_list.rows}
    unknown = set(crop_assignments) - crop_names
    if unknown:
        raise InvalidCropAssignmentError(f"not in the list: {', '.join(sorted(unknown))}")
    names = land_use_names()
    bad_codes = {code for code in crop_assignments.values() if code not in names}
    if bad_codes:
        raise InvalidCropAssignmentError(f"unknown Land Use: {', '.join(sorted(bad_codes))}")

    def land_use(crop: str) -> tuple[str, str] | None:
        if crop in crop_assignments:
            code = crop_assignments[crop]
            return (code, names[code])
        return crops.land_use(crop)

    by_field: dict[int, list[int]] = defaultdict(list)
    for index, row in enumerate(field_list.rows):
        by_field[row.field_number].append(index)

    fields = []
    for number, indexes in sorted(by_field.items()):
        first = field_list.rows[indexes[0]]
        code, name = crops.field_land_use(first.field_land_use)
        geometry = reference.fields.get(number) if reference else None
        fields.append(
            PlannedField(
                number=number,
                name=first.field_name,
                land_use_code=code,
                land_use_name=name,
                # farmdok fills in the Field size only after an AMA import into farmdok.
                declared_area_ha=first.field_area_ha
                if first.field_area_ha is not None
                else sum((field_list.rows[i].plot_area_ha for i in indexes), Decimal(0)),
                geometry=geometry,
                match=GeometryMatch.FIELD if geometry is not None else GeometryMatch.NONE,
            )
        )

    borrowed = _borrow(field_list, reference) if reference else {}
    plots = []
    for row in sorted(field_list.rows, key=lambda r: (r.field_number, r.plot_number)):
        found = borrowed.get((row.field_number, row.plot_number))
        field_geometry = reference.fields.get(row.field_number) if reference else None
        if found is not None:
            geometry, match = found
        elif field_geometry is not None:
            geometry, match = field_geometry, GeometryMatch.FIELD
        else:
            geometry, match = None, GeometryMatch.NONE
        plots.append(
            PlannedPlot(
                field_number=row.field_number,
                number=row.plot_number,
                crop=row.crop,
                land_use=land_use(row.crop),
                declared_area_ha=row.plot_area_ha,
                geometry=geometry,
                match=match,
            )
        )

    counts: dict[str, int] = defaultdict(int)
    for planned in plots:
        if planned.land_use is None:
            counts[planned.crop] += 1
    return FieldListPlan(
        harvest_year=field_list.harvest_year,
        reference_year=reference.harvest_year if reference else None,
        fields=tuple(fields),
        plots=tuple(plots),
        unknown_crops=tuple(UnknownCrop(name, n) for name, n in sorted(counts.items())),
    )


def _borrow[G](
    field_list: FieldList, reference: Reference[G]
) -> dict[tuple[int, int], tuple[G, GeometryMatch]]:
    """Which reference Plot each listed Plot takes its geometry from."""
    areas = reference.plot_areas
    rows = {(r.field_number, r.plot_number): r.plot_area_ha for r in field_list.rows}

    def close(a: Decimal, b: Decimal, tolerance: Decimal) -> bool:
        return b > 0 and abs(a - b) <= max(tolerance * b, MIN_TOLERANCE_HA)

    found: dict[tuple[int, int], tuple[G, GeometryMatch]] = {}
    used: set[tuple[int, int]] = set()
    for key, area in rows.items():
        geometry = reference.plots.get(key)
        if geometry is None:
            continue
        if not areas or (key in areas and close(area, areas[key], NUMBER_TOLERANCE)):
            found[key] = (geometry, GeometryMatch.PLOT)
            used.add(key)
    if not areas:
        return found
    for key, area in sorted(rows.items()):
        if key in found:
            continue
        candidates = [
            other
            for other in reference.plots
            if other[0] == key[0]
            and other not in used
            and other in areas
            and close(area, areas[other], AREA_TOLERANCE)
        ]
        if len(candidates) == 1:
            found[key] = (reference.plots[candidates[0]], GeometryMatch.AREA)
            used.add(candidates[0])
    return found


def nearest_year(target: int, candidates: set[int]) -> int | None:
    """The default year to borrow from: the closest, the later one on a tie."""
    others = candidates - {target}
    return min(others, key=lambda y: (abs(y - target), -y)) if others else None
