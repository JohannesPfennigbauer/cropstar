"""Reconciling an area declaration with the Fields and Plots that already exist.

Every declared Field and Plot ends up either assigned to an existing one — the same piece of
land, updated in place so it keeps its Tasks and Operations — or new, without history.
Areas that are unchanged or covered ≥ 90 % by exactly one existing area are suggested;
everything else is decided by the Admin. Existing areas nobody is assigned to are removed.
Nothing is ever copied or inherited.

Pure: existing areas, a declaration and the Admin's assignments in, a plan out. Preview and
apply run the same code. Nothing here assumes both sides belong to the same Harvest Year.
"""

import enum
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import partial
from typing import Any

import shapely
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from cropstar_api.eama import AreaDeclaration, DeclaredField, DeclaredPlot

# "Substantially the same piece of land": at least this share of the declared area lies on
# one existing area.
SUGGESTION_COVERAGE = 0.9
# Geometry this close to the existing one is unchanged: re-exports shift vertices slightly.
UNCHANGED_SHARE = 0.001
UNCHANGED_M2 = 1.0
# Neighbouring areas share edges; overlaps this small are drawing noise, not candidates.
MIN_OVERLAP_M2 = 1.0


class AreaStatus(enum.StrEnum):
    NEW = "new"
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    UNDECIDED = "undecided"


class AreaChange(enum.StrEnum):
    NUMBER = "number"
    # A Plot that now lies on another Field.
    FIELD = "field"
    NAME = "name"
    LAND_USE = "land_use"
    DECLARED_AREA = "declared_area"
    GEOMETRY = "geometry"
    # The geometry so far came from elsewhere (open data, borrowed); now it is the export.
    SOURCE = "source"


class AreaUploadBlocker(enum.StrEnum):
    HARVEST_YEAR_LOCKED = "harvest_year_locked"
    UNDECIDED_AREAS = "undecided_areas"
    REMOVES_REFERENCED_AREAS = "removes_referenced_areas"


class InvalidAssignmentError(ValueError):
    """The assignments name an area that is not declared, or an unknown or reused target."""


@dataclass(frozen=True)
class ExistingArea:
    """A Field or Plot as it is now. Geometry in a metric CRS (EPSG:31287)."""

    id: uuid.UUID
    number: int
    land_use_code: str
    land_use_name: str
    declared_area_ha: Decimal
    geometry: BaseGeometry
    from_eama: bool
    # Whether Tasks or Operations refer to it, so removing it would lose recorded work.
    referenced: bool
    name: str | None = None
    # The Field a Plot lies on.
    field_id: uuid.UUID | None = None


@dataclass(frozen=True)
class Candidate:
    id: uuid.UUID
    # The share of the declared area lying on the existing one.
    coverage: float


@dataclass(frozen=True)
class Entry:
    """What happens to one declared Field or Plot."""

    key: str
    # The existing area it is assigned to; None when it is new or still undecided.
    target: uuid.UUID | None
    decided: bool
    # Whether the decision is the suggestion rather than the Admin's own choice.
    suggested: bool
    status: AreaStatus
    changes: tuple[AreaChange, ...]
    # Overlapping existing areas, most covered first.
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class Plan:
    fields: tuple[Entry, ...]
    plots: tuple[Entry, ...]
    removed_fields: tuple[uuid.UUID, ...]
    removed_plots: tuple[uuid.UUID, ...]
    blockers: tuple[AreaUploadBlocker, ...]


def field_key(number: int) -> str:
    return f"field-{number}"


def plot_key(field_number: int, number: int) -> str:
    return f"plot-{field_number}-{number}"


def reconcile(
    existing_fields: Sequence[ExistingArea],
    existing_plots: Sequence[ExistingArea],
    declaration: AreaDeclaration,
    assignments: Mapping[str, uuid.UUID | None],
    *,
    locked: bool = False,
) -> Plan:
    """Assignments map a declared area's key to an existing id, or to None for "new"; keys
    left out take the suggestion, if there is one."""
    field_keys = [field_key(f.number) for f in declaration.fields]
    plot_keys = [plot_key(p.field_number, p.number) for p in declaration.plots]
    unknown = set(assignments) - {*field_keys, *plot_keys}
    if unknown:
        raise InvalidAssignmentError(f"unknown areas: {', '.join(sorted(unknown))}")

    fields = _Matcher(
        existing_fields,
        [(key, f.geometry) for key, f in zip(field_keys, declaration.fields, strict=True)],
        {key: assignments[key] for key in field_keys if key in assignments},
    )
    plots = _Matcher(
        existing_plots,
        [(key, p.geometry) for key, p in zip(plot_keys, declaration.plots, strict=True)],
        {key: assignments[key] for key in plot_keys if key in assignments},
    )

    field_entries = tuple(
        fields.entry(key, partial(_field_changes, declared))
        for key, declared in zip(field_keys, declaration.fields, strict=True)
    )
    field_by_number = {
        declared.number: entry
        for declared, entry in zip(declaration.fields, field_entries, strict=True)
    }
    plot_entries = tuple(
        plots.entry(key, partial(_plot_changes, declared, field_by_number[declared.field_number]))
        for key, declared in zip(plot_keys, declaration.plots, strict=True)
    )

    removed_fields = fields.removed()
    removed_plots = plots.removed()
    referenced = {a.id for a in [*existing_fields, *existing_plots] if a.referenced}
    blockers = []
    if locked:
        blockers.append(AreaUploadBlocker.HARVEST_YEAR_LOCKED)
    if any(not e.decided for e in (*field_entries, *plot_entries)):
        blockers.append(AreaUploadBlocker.UNDECIDED_AREAS)
    if referenced.intersection((*removed_fields, *removed_plots)):
        blockers.append(AreaUploadBlocker.REMOVES_REFERENCED_AREAS)
    return Plan(field_entries, plot_entries, removed_fields, removed_plots, tuple(blockers))


@dataclass(frozen=True)
class _Overlap:
    coverage: float
    unchanged: bool


class _Matcher:
    """Candidates, suggestions and decisions for one kind of area (Fields or Plots)."""

    def __init__(
        self,
        existing: Sequence[ExistingArea],
        declared: Sequence[tuple[str, dict[str, Any]]],
        assignments: Mapping[str, uuid.UUID | None],
    ) -> None:
        self.existing = {area.id: area for area in existing}
        unknown = {t for t in assignments.values() if t is not None} - self.existing.keys()
        if unknown:
            raise InvalidAssignmentError(f"unknown targets: {', '.join(map(str, unknown))}")
        reused = [t for t, n in Counter(assignments.values()).items() if t is not None and n > 1]
        if reused:
            raise InvalidAssignmentError(f"assigned twice: {', '.join(map(str, reused))}")

        self.overlaps = self._overlaps(declared)
        suggestions = self._suggestions(declared)
        chosen = {t for t in assignments.values() if t is not None}
        self.decisions: dict[str, tuple[uuid.UUID | None, bool]] = {}
        for key, _ in declared:
            if key in assignments:
                self.decisions[key] = (assignments[key], False)
            elif key in suggestions and suggestions[key] not in chosen:
                # An existing area the Admin assigned elsewhere is no longer free.
                self.decisions[key] = (suggestions[key], True)

    def _overlaps(
        self, declared: Sequence[tuple[str, dict[str, Any]]]
    ) -> dict[str, dict[uuid.UUID, _Overlap]]:
        ids = list(self.existing)
        shapes = [self.existing[i].geometry for i in ids]
        tree = shapely.STRtree(shapes)
        overlaps: dict[str, dict[uuid.UUID, _Overlap]] = {}
        for key, geojson in declared:
            new = _valid(shape(geojson))
            found = {}
            for index in tree.query(new, predicate="intersects"):
                old = shapes[index]
                shared = new.intersection(old).area
                if shared < MIN_OVERLAP_M2:
                    continue
                tolerance = max(UNCHANGED_M2, UNCHANGED_SHARE * old.area)
                found[ids[index]] = _Overlap(
                    coverage=min(shared / new.area, 1.0) if new.area else 0.0,
                    unchanged=new.symmetric_difference(old).area <= tolerance,
                )
            overlaps[key] = found
        return overlaps

    def _suggestions(
        self, declared: Sequence[tuple[str, dict[str, Any]]]
    ) -> dict[str, uuid.UUID | None]:
        if not self.existing:
            # Nothing to inherit from: the first upload creates everything.
            return {key: None for key, _ in declared}
        proposals: dict[uuid.UUID, list[tuple[str, bool]]] = defaultdict(list)
        for key, _ in declared:
            overlaps = self.overlaps[key]
            unchanged = [i for i, o in overlaps.items() if o.unchanged]
            covering = [i for i, o in overlaps.items() if o.coverage >= SUGGESTION_COVERAGE]
            if len(unchanged) == 1:
                proposals[unchanged[0]].append((key, True))
            elif len(covering) == 1:
                proposals[covering[0]].append((key, False))
        suggestions: dict[str, uuid.UUID | None] = {}
        for target, keys in proposals.items():
            # One existing area can only stay one area; an unchanged one wins, else nobody.
            identical = [key for key, unchanged in keys if unchanged]
            if len(keys) == 1:
                suggestions[keys[0][0]] = target
            elif len(identical) == 1:
                suggestions[identical[0]] = target
        return suggestions

    def entry(self, key: str, changes: Callable[[ExistingArea], list[AreaChange]]) -> Entry:
        candidates = tuple(
            Candidate(i, o.coverage)
            for i, o in sorted(self.overlaps[key].items(), key=lambda item: -item[1].coverage)
        )
        if key not in self.decisions:
            return Entry(key, None, False, False, AreaStatus.UNDECIDED, (), candidates)
        target, suggested = self.decisions[key]
        if target is None:
            return Entry(key, None, True, suggested, AreaStatus.NEW, (), candidates)
        overlap = self.overlaps[key].get(target)
        found: list[AreaChange] = changes(self.existing[target])
        if overlap is None or not overlap.unchanged:
            found.append(AreaChange.GEOMETRY)
        if not self.existing[target].from_eama:
            found.append(AreaChange.SOURCE)
        found.sort(key=list(AreaChange).index)
        status = AreaStatus.CHANGED if found else AreaStatus.UNCHANGED
        return Entry(key, target, True, suggested, status, tuple(found), candidates)

    def removed(self) -> tuple[uuid.UUID, ...]:
        kept = {target for target, _ in self.decisions.values()}
        return tuple(i for i in self.existing if i not in kept)


def _field_changes(declared: DeclaredField, old: ExistingArea) -> list[AreaChange]:
    found = _common_changes(old, declared.number, declared.land_use_code, declared.land_use_name)
    if old.name != declared.name:
        found.append(AreaChange.NAME)
    if old.declared_area_ha.compare(declared.declared_area_ha) != 0:
        found.append(AreaChange.DECLARED_AREA)
    return found


def _plot_changes(declared: DeclaredPlot, field: Entry, old: ExistingArea) -> list[AreaChange]:
    found = _common_changes(old, declared.number, declared.land_use_code, declared.land_use_name)
    # The Plot moves when its declared Field is another or a new one; unknown while undecided.
    if field.decided and field.target != old.field_id:
        found.append(AreaChange.FIELD)
    if old.declared_area_ha.compare(declared.declared_area_ha) != 0:
        found.append(AreaChange.DECLARED_AREA)
    return found


def _common_changes(
    old: ExistingArea, number: int, land_use_code: str, land_use_name: str
) -> list[AreaChange]:
    found = []
    if old.number != number:
        found.append(AreaChange.NUMBER)
    if (old.land_use_code, old.land_use_name) != (land_use_code, land_use_name):
        found.append(AreaChange.LAND_USE)
    return found


def _valid(geometry: BaseGeometry) -> BaseGeometry:
    return geometry if geometry.is_valid else shapely.make_valid(geometry)
