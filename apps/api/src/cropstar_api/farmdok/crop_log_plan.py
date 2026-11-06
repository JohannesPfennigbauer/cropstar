"""Planning a farmdok crop production log import: one Done Task per entry.

Each entry becomes a Task named after the activity, with one Operation per Plot. Plots are
found by Field number and crop (the crop's AMA Land Use). farmdok logs work per Field, so
an entry applies to every Plot of the Field with that crop. The activity gives the Operation
Type and a detail (implement, sowing purpose); the product becomes a Farm Input for sowing
and fertilisation and a note otherwise; amounts are normalised into the details' units.

What cannot be decided is listed as unresolved: unknown activities, unknown products, and
entries whose Plots are missing or ambiguous. The Admin's resolutions, and assignments
remembered from earlier imports, are inputs, so preview and apply run the same code.

Pure: no database.
"""

import csv
import enum
import re
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from functools import cache
from importlib.resources import files
from typing import Any

from pydantic import ValidationError

from cropstar_api.farmdok import crops
from cropstar_api.farmdok.crop_log import CropLog, CropLogEntry
from cropstar_api.models import FarmInputKind, FarmInputUnit
from cropstar_api.nutrients import compatible
from cropstar_api.operation_details import (
    FertilisationDetails,
    FertilisationUnit,
    HarvestDetails,
    HarvestedProduct,
    MechanicalWeedControlDetails,
    MulchingDetails,
    OperationDetails,
    SowingDetails,
    SowingPurpose,
    SowingUnit,
    TillageDetails,
    from_stored,
)

# Operation Types whose product is a Farm Input, and of which kind.
INPUT_KINDS = {"sowing": FarmInputKind.SEED, "fertilisation": FarmInputKind.FERTILISER}
_SOWING_UNITS = {
    "kg/ha": (SowingUnit.KG_PER_HA, Decimal(1)),
    "kö/ha": (SowingUnit.SEEDS_PER_HA, Decimal(1)),
    "kö/m²": (SowingUnit.SEEDS_PER_M2, Decimal(1)),
}
_FERTILISATION_UNITS = {
    "kg/ha": (FertilisationUnit.KG_PER_HA, Decimal(1)),
    "t/ha": (FertilisationUnit.T_PER_HA, Decimal(1)),
    "m³/ha": (FertilisationUnit.M3_PER_HA, Decimal(1)),
    "l/ha": (FertilisationUnit.L_PER_HA, Decimal(1)),
}
# Yields are recorded in t/ha.
_YIELD_UNITS = {"t/ha": Decimal(1), "kg/ha": Decimal("0.001"), "dt/ha": Decimal("0.1")}
# A Farm Input created for a fertilisation states its contents per the amount's unit.
_INPUT_UNIT_FOR = {
    FertilisationUnit.KG_PER_HA: FarmInputUnit.HUNDRED_KG,
    FertilisationUnit.T_PER_HA: FarmInputUnit.TONNE,
    FertilisationUnit.M3_PER_HA: FarmInputUnit.CUBIC_METRE,
    FertilisationUnit.L_PER_HA: FarmInputUnit.CUBIC_METRE,
}


class Problem(enum.StrEnum):
    UNKNOWN_ACTIVITY = "unknown_activity"
    UNKNOWN_PRODUCT = "unknown_product"
    # The chosen Farm Input's contents do not fit the amount's unit.
    UNIT_MISMATCH = "unit_mismatch"
    UNKNOWN_FIELD = "unknown_field"
    # The crop does not map to a Land Use, so the Plot cannot be told.
    UNKNOWN_CROP = "unknown_crop"
    NO_MATCHING_PLOT = "no_matching_plot"


class InvalidResolutionError(ValueError):
    """A resolution names something unknown: an activity, product, entry, Plot, Farm Input
    or Operation Type, or asks to create seed whose Land Use cannot be told."""


@dataclass(frozen=True)
class YearPlot:
    id: uuid.UUID
    field_number: int
    number: int
    land_use_code: str


@dataclass(frozen=True)
class KnownInput:
    id: uuid.UUID
    name: str
    kind: FarmInputKind
    unit: FarmInputUnit | None
    archived: bool


@dataclass(frozen=True)
class ProductChoice:
    """Exactly one: an existing Farm Input, a new one named like the product, or none."""

    farm_input_id: uuid.UUID | None = None
    create: bool = False


NO_INPUT = ProductChoice()


@dataclass(frozen=True)
class Resolutions:
    # Activity → Operation Type code, or None to skip its entries.
    activities: Mapping[str, str | None] = field(default_factory=dict)
    products: Mapping[str, ProductChoice] = field(default_factory=dict)
    # Spreadsheet row → Plot ids, or None to skip the entry.
    entries: Mapping[int, Sequence[uuid.UUID] | None] = field(default_factory=dict)


@dataclass(frozen=True)
class NewInput:
    name: str
    kind: FarmInputKind
    unit: FarmInputUnit | None
    land_use_code: str | None


@dataclass(frozen=True)
class PlannedTask:
    row: int
    title: str
    performed_on: date
    operation_type: str
    plot_ids: tuple[uuid.UUID, ...]
    details: OperationDetails
    # A Farm Input to create on apply; its id then goes into the details.
    new_input: str | None


@dataclass(frozen=True)
class Unresolved:
    problem: Problem
    # The activity, the product, or the entry's row.
    key: str
    rows: tuple[int, ...]
    # Field numbers (Plot problems) or the Operation Type (product problems).
    context: tuple[str, ...] = ()


@dataclass(frozen=True)
class CropLogPlan:
    harvest_year: int
    entry_count: int
    tasks: tuple[PlannedTask, ...]
    skipped_rows: tuple[int, ...]
    unresolved: tuple[Unresolved, ...]
    new_inputs: tuple[NewInput, ...]


@dataclass(frozen=True)
class _Activity:
    operation_type: str
    detail: str | None


def plan(
    log: CropLog,
    plots: Sequence[YearPlot],
    inputs: Sequence[KnownInput],
    operation_types: set[str],
    remembered_activities: Mapping[str, str | None],
    remembered_products: Mapping[str, uuid.UUID | None],
    resolutions: Resolutions,
    remembered_crops: Mapping[str, str] | None = None,
) -> CropLogPlan:
    """`remembered_crops` maps farmdok crop names to AMA Land Use codes, as the Admin
    assigned them when importing a field list."""
    _check(log, plots, inputs, operation_types, resolutions)
    inputs_by_id = {i.id: i for i in inputs}
    plots_by_field: dict[int, list[YearPlot]] = defaultdict(list)
    for plot in plots:
        plots_by_field[plot.field_number].append(plot)

    unresolved: dict[tuple[Problem, str], list[int]] = defaultdict(list)
    context: dict[tuple[Problem, str], tuple[str, ...]] = {}
    tasks: list[PlannedTask] = []
    skipped: list[int] = []
    new_inputs: dict[str, NewInput] = {}

    for entry in log.entries:
        if resolutions.entries.get(entry.row, ()) is None:
            skipped.append(entry.row)
            continue
        activity = _activity(entry.activity, remembered_activities, resolutions)
        if activity is _SKIP:
            skipped.append(entry.row)
            continue
        problems_before = sum(len(rows) for rows in unresolved.values())
        if activity is None:
            unresolved[(Problem.UNKNOWN_ACTIVITY, entry.activity)].append(entry.row)

        plot_ids = _plots(
            entry, plots_by_field, remembered_crops or {}, resolutions, unresolved, context
        )

        input_id: uuid.UUID | None = None
        new_input: str | None = None
        if (
            isinstance(activity, _Activity)
            and entry.product
            and activity.operation_type in INPUT_KINDS
        ):
            kind = INPUT_KINDS[activity.operation_type]
            choice = _product(entry.product, kind, inputs, remembered_products, resolutions)
            key = (Problem.UNKNOWN_PRODUCT, entry.product)
            if choice is None:
                unresolved[key].append(entry.row)
                context[key] = (activity.operation_type,)
            elif choice.create:
                if kind is FarmInputKind.SEED and not can_create_seed(entry.product):
                    raise InvalidResolutionError(f"seed needs a Land Use: {entry.product}")
                new_input = entry.product
                new_inputs[entry.product] = _new_input(entry, kind)
            elif choice.farm_input_id is not None:
                chosen = inputs_by_id[choice.farm_input_id]
                if chosen.kind is not kind:
                    raise InvalidResolutionError(f"{entry.product} needs a {kind}")
                if not _fits(entry, activity.operation_type, chosen):
                    mismatch = (Problem.UNIT_MISMATCH, entry.product)
                    unresolved[mismatch].append(entry.row)
                    context[mismatch] = (activity.operation_type,)
                input_id = choice.farm_input_id

        if sum(len(rows) for rows in unresolved.values()) > problems_before:
            continue
        assert isinstance(activity, _Activity) and plot_ids is not None
        tasks.append(
            PlannedTask(
                row=entry.row,
                title=entry.activity,
                performed_on=entry.performed_on,
                operation_type=activity.operation_type,
                plot_ids=plot_ids,
                details=_details(entry, activity, input_id, new_input is not None),
                new_input=new_input,
            )
        )

    return CropLogPlan(
        harvest_year=log.harvest_year,
        entry_count=len(log.entries),
        tasks=tuple(tasks),
        skipped_rows=tuple(skipped),
        unresolved=tuple(
            Unresolved(problem, key, tuple(rows), context.get((problem, key), ()))
            for (problem, key), rows in unresolved.items()
        ),
        new_inputs=tuple(new_inputs.values()),
    )


def can_create_seed(product: str) -> bool:
    return _seed_land_use(product) is not None


# ── Internals ───────────────────────────────────────────────────────────────

_SKIP = object()


@cache
def _table() -> dict[str, _Activity]:
    text = (files("cropstar_api.farmdok") / "activities.csv").read_text("utf-8")
    rows = csv.DictReader(line for line in text.splitlines() if not line.startswith("#"))
    return {
        _normalise(row["activity"]): _Activity(row["operation_type"], row["detail"] or None)
        for row in rows
    }


def _normalise(name: str) -> str:
    return " ".join(name.split()).casefold()


def _activity(name: str, remembered: Mapping[str, str | None], resolutions: Resolutions) -> Any:
    """The activity's mapping, `_SKIP`, or None when nobody knows it."""
    if name in resolutions.activities:
        chosen = resolutions.activities[name]
        return _SKIP if chosen is None else _Activity(chosen, None)
    if name in remembered:
        chosen = remembered[name]
        return _SKIP if chosen is None else _Activity(chosen, None)
    return _table().get(_normalise(name))


def _product(
    name: str,
    kind: FarmInputKind,
    inputs: Sequence[KnownInput],
    remembered: Mapping[str, uuid.UUID | None],
    resolutions: Resolutions,
) -> ProductChoice | None:
    if name in resolutions.products:
        return resolutions.products[name]
    if name in remembered:
        return ProductChoice(farm_input_id=remembered[name])
    same = [
        i
        for i in inputs
        if i.kind is kind and not i.archived and _normalise(i.name) == _normalise(name)
    ]
    return ProductChoice(farm_input_id=same[0].id) if len(same) == 1 else None


def _plots(
    entry: CropLogEntry,
    plots_by_field: Mapping[int, list[YearPlot]],
    remembered_crops: Mapping[str, str],
    resolutions: Resolutions,
    unresolved: dict[tuple[Problem, str], list[int]],
    context: dict[tuple[Problem, str], tuple[str, ...]],
) -> tuple[uuid.UUID, ...] | None:
    assigned = resolutions.entries.get(entry.row)
    if assigned is not None:
        return tuple(assigned)
    code = remembered_crops.get(entry.crop) or (crops.land_use(entry.crop) or (None,))[0]
    found: list[uuid.UUID] = []
    failures: list[tuple[Problem, int]] = []
    for number in entry.field_numbers:
        candidates = plots_by_field.get(number, [])
        if not candidates:
            failures.append((Problem.UNKNOWN_FIELD, number))
            continue
        if code is None:
            failures.append((Problem.UNKNOWN_CROP, number))
            continue
        matching = [p.id for p in candidates if p.land_use_code == code]
        if matching:
            found.extend(matching)
        else:
            failures.append((Problem.NO_MATCHING_PLOT, number))
    if failures:
        # One entry, one decision: the Admin assigns all its Plots at once.
        key = (failures[0][0], str(entry.row))
        unresolved[key].append(entry.row)
        context[key] = tuple(str(n) for n in entry.field_numbers)
        return None
    return tuple(found)


def _fits(entry: CropLogEntry, operation_type: str, chosen: KnownInput) -> bool:
    if operation_type != "fertilisation" or entry.unit is None or chosen.unit is None:
        return True
    unit = _FERTILISATION_UNITS.get(_unit_key(entry.unit))
    return unit is None or compatible(unit[0], chosen.unit)


def _new_input(entry: CropLogEntry, kind: FarmInputKind) -> NewInput:
    assert entry.product is not None
    if kind is FarmInputKind.SEED:
        land_use = _seed_land_use(entry.product)
        return NewInput(entry.product, kind, None, land_use[0] if land_use else None)
    unit = _FERTILISATION_UNITS.get(_unit_key(entry.unit or ""))
    return NewInput(entry.product, kind, _INPUT_UNIT_FOR[unit[0]] if unit else None, None)


def _seed_land_use(product: str) -> tuple[str, str] | None:
    # farmdok names seed after its crop, sometimes with the unit: "Sojabohne (Körner/m²)".
    return crops.land_use(product) or crops.land_use(re.sub(r"\s*\([^)]*\)\s*$", "", product))


def _unit_key(unit: str) -> str:
    return unit.strip().casefold().replace("m2", "m²").replace("m3", "m³")


def _details(
    entry: CropLogEntry, activity: _Activity, input_id: uuid.UUID | None, creating: bool
) -> OperationDetails:
    """`creating`: the Farm Input is created on apply, so the product needs no note."""
    detail = activity.detail
    notes: list[str] = []
    amount, unit = entry.amount, _unit_key(entry.unit or "")
    # A product on work without one (e.g. tillage) is kept as a note.
    product_note = [entry.product] if entry.product else []
    try:
        match activity.operation_type:
            case "tillage":
                return TillageDetails(implement=detail, note=_note(product_note))
            case "mechanical_weed_control":
                return MechanicalWeedControlDetails(implement=detail, note=_note(product_note))
            case "mulching":
                return MulchingDetails(note=_note(product_note))
            case "sowing":
                sowing = _SOWING_UNITS.get(unit)
                if amount is not None and sowing is None:
                    notes.append(f"{amount} {entry.unit}")
                if input_id is None and not creating and entry.product:
                    notes.append(entry.product)
                return SowingDetails(
                    purpose=SowingPurpose(detail) if detail else None,
                    farm_input_id=input_id,
                    rate=float(amount * sowing[1]) if amount is not None and sowing else None,
                    unit=sowing[0] if amount is not None and sowing else None,
                    note=_note(notes),
                )
            case "fertilisation":
                fertilisation = _FERTILISATION_UNITS.get(unit)
                if amount is not None and fertilisation is None:
                    notes.append(f"{amount} {entry.unit}")
                if input_id is None and not creating and entry.product:
                    notes.append(entry.product)
                return FertilisationDetails(
                    farm_input_id=input_id,
                    amount=float(amount * fertilisation[1])
                    if amount is not None and fertilisation
                    else None,
                    unit=fertilisation[0] if amount is not None and fertilisation else None,
                    note=_note(notes),
                )
            case "harvest":
                factor = _YIELD_UNITS.get(unit)
                if amount is not None and factor is None:
                    notes.append(f"{amount} {entry.unit}")
                if entry.product:
                    notes.append(entry.product)
                return HarvestDetails(
                    product=HarvestedProduct(detail) if detail else None,
                    yield_t_per_ha=float(round(amount * factor, 3))
                    if amount is not None and factor
                    else None,
                    note=_note(notes),
                )
    except ValidationError:
        pass
    # An Operation Type the Admin chose for an unknown activity: keep what farmdok said.
    return _plain(activity.operation_type, entry)


def _note(parts: list[str]) -> str | None:
    return " · ".join(dict.fromkeys(parts)) or None


def _plain(operation_type: str, entry: CropLogEntry) -> OperationDetails:
    parts = [entry.product or "", f"{entry.amount} {entry.unit}" if entry.amount else ""]
    details: dict[str, Any] = {"type": operation_type, "note": _note([p for p in parts if p])}
    parsed = from_stored(details)
    assert parsed is not None
    return parsed


def _check(
    log: CropLog,
    plots: Sequence[YearPlot],
    inputs: Sequence[KnownInput],
    operation_types: set[str],
    resolutions: Resolutions,
) -> None:
    activities = {e.activity for e in log.entries}
    products = {e.product for e in log.entries if e.product}
    rows = {e.row for e in log.entries}
    plot_ids = {p.id for p in plots}
    input_ids = {i.id for i in inputs}
    if set(resolutions.activities) - activities:
        raise InvalidResolutionError("unknown activity")
    if {t for t in resolutions.activities.values() if t is not None} - operation_types:
        raise InvalidResolutionError("unknown Operation Type")
    if set(resolutions.products) - products:
        raise InvalidResolutionError("unknown product")
    for choice in resolutions.products.values():
        if choice.farm_input_id is not None and choice.farm_input_id not in input_ids:
            raise InvalidResolutionError("unknown Farm Input")
        if choice.create and choice.farm_input_id is not None:
            raise InvalidResolutionError("create or choose, not both")
    if set(resolutions.entries) - rows:
        raise InvalidResolutionError("unknown entry")
    for assigned in resolutions.entries.values():
        if assigned is not None and (not assigned or set(assigned) - plot_ids):
            raise InvalidResolutionError("unknown Plot")
