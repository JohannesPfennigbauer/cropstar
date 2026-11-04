import uuid
from decimal import Decimal
from typing import Any

import pytest
from shapely.geometry import box, shape

from cropstar_api.area_reconciliation import (
    AreaChange,
    AreaStatus,
    AreaUploadBlocker,
    ExistingArea,
    InvalidAssignmentError,
    Plan,
    reconcile,
)
from cropstar_api.eama import AreaDeclaration, DeclaredField, DeclaredPlot


def square(x: float, size: float = 100, y: float = 0) -> dict[str, Any]:
    """A square in metres, as GeoJSON in the AMA CRS."""
    ring = [[x, y], [x + size, y], [x + size, y + size], [x, y + size], [x, y]]
    return {"type": "MultiPolygon", "coordinates": [[ring]]}


def declared_field(number: int, geometry: dict[str, Any], **changes: Any) -> DeclaredField:
    values: dict[str, Any] = {
        "number": number,
        "name": f"Feld {number}",
        "land_use_code": "A",
        "land_use_name": "ACKERLAND",
        "declared_area_ha": Decimal("1.0000"),
        "geometry": geometry,
    }
    return DeclaredField(**(values | changes))


def declared_plot(
    field_number: int, number: int, geometry: dict[str, Any], **changes: Any
) -> DeclaredPlot:
    values: dict[str, Any] = {
        "field_number": field_number,
        "number": number,
        "land_use_code": "142",
        "land_use_name": "WINTERROGGEN",
        "declared_area_ha": Decimal("1.0000"),
        "geometry": geometry,
    }
    return DeclaredPlot(**(values | changes))


def existing_field(number: int, geometry: dict[str, Any], **changes: Any) -> ExistingArea:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "number": number,
        "name": f"Feld {number}",
        "land_use_code": "A",
        "land_use_name": "ACKERLAND",
        "declared_area_ha": Decimal("1.0000"),
        "geometry": shape(geometry),
        "from_eama": True,
        "referenced": False,
    }
    return ExistingArea(**(values | changes))


def existing_plot(
    field: ExistingArea, number: int, geometry: dict[str, Any], **changes: Any
) -> ExistingArea:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "field_id": field.id,
        "number": number,
        "land_use_code": "142",
        "land_use_name": "WINTERROGGEN",
        "declared_area_ha": Decimal("1.0000"),
        "geometry": shape(geometry),
        "from_eama": True,
        "referenced": False,
    }
    return ExistingArea(**(values | changes))


def declaration(fields: list[DeclaredField], plots: list[DeclaredPlot]) -> AreaDeclaration:
    return AreaDeclaration(2026, tuple(fields), tuple(plots))


def statuses(plan: Plan) -> list[AreaStatus]:
    return [entry.status for entry in (*plan.fields, *plan.plots)]


# One Field with two Plots side by side, as they exist now.
FIELD = existing_field(1, square(0, 200))
LEFT = existing_plot(FIELD, 1, square(0))
RIGHT = existing_plot(FIELD, 2, square(100))


def same_export(**plot_changes: Any) -> AreaDeclaration:
    return declaration(
        [declared_field(1, square(0, 200))],
        [
            declared_plot(1, 1, plot_changes.pop("geometry", square(0)), **plot_changes),
            declared_plot(1, 2, square(100)),
        ],
    )


def test_an_empty_year_suggests_creating_everything() -> None:
    plan = reconcile([], [], same_export(), {})

    assert statuses(plan) == [AreaStatus.NEW] * 3
    assert all(entry.decided and entry.suggested for entry in (*plan.fields, *plan.plots))
    assert plan.blockers == ()


def test_the_same_export_again_is_all_unchanged() -> None:
    plan = reconcile([FIELD], [LEFT, RIGHT], same_export(), {})

    assert statuses(plan) == [AreaStatus.UNCHANGED] * 3
    assert [entry.target for entry in plan.plots] == [LEFT.id, RIGHT.id]
    assert (plan.removed_fields, plan.removed_plots, plan.blockers) == ((), (), ())


def test_tiny_differences_in_geometry_do_not_count_as_changes() -> None:
    nudged = square(0.004, 100.0)

    plan = reconcile([FIELD], [LEFT, RIGHT], same_export(geometry=nudged), {})

    assert plan.plots[0].status == AreaStatus.UNCHANGED


def test_changed_attributes_are_listed() -> None:
    export = same_export(
        land_use_code="311", land_use_name="KÖRNERMAIS", declared_area_ha=Decimal("0.9500")
    )

    plan = reconcile([FIELD], [LEFT, RIGHT], export, {})

    assert plan.plots[0].status == AreaStatus.CHANGED
    assert plan.plots[0].changes == (AreaChange.LAND_USE, AreaChange.DECLARED_AREA)


def test_an_area_covered_mostly_by_one_existing_area_is_suggested_whatever_its_number() -> None:
    # Plot 1 shrank by 5 % and is now Plot 7; most of it lies on the old Plot 1.
    shrunk = declared_plot(1, 7, square(5, 95))
    export = declaration(
        [declared_field(1, square(0, 200))], [shrunk, declared_plot(1, 2, square(100))]
    )

    plan = reconcile([FIELD], [LEFT, RIGHT], export, {})

    entry = plan.plots[0]
    assert (entry.target, entry.suggested, entry.status) == (LEFT.id, True, AreaStatus.CHANGED)
    assert entry.changes == (AreaChange.NUMBER, AreaChange.GEOMETRY)


def test_the_same_number_on_different_ground_is_not_suggested() -> None:
    export = declaration(
        [declared_field(1, square(0, 200))],
        [declared_plot(1, 1, square(5_000)), declared_plot(1, 2, square(100))],
    )

    plan = reconcile([FIELD], [LEFT, RIGHT], export, {})

    assert plan.plots[0].status == AreaStatus.UNDECIDED
    assert plan.plots[0].candidates == ()
    assert plan.removed_plots == (LEFT.id,)
    assert plan.blockers == (AreaUploadBlocker.UNDECIDED_AREAS,)


def test_less_than_the_coverage_threshold_offers_candidates_but_suggests_nothing() -> None:
    # Half on the old Plot 1, half on new ground.
    export = declaration(
        [declared_field(1, square(0, 200))],
        [declared_plot(1, 1, square(-50)), declared_plot(1, 2, square(100))],
    )

    plan = reconcile([FIELD], [LEFT, RIGHT], export, {})

    entry = plan.plots[0]
    assert entry.status == AreaStatus.UNDECIDED
    assert [c.id for c in entry.candidates] == [LEFT.id]
    assert entry.candidates[0].coverage == pytest.approx(0.5)


def test_the_admin_decides_what_was_not_suggested() -> None:
    export = declaration(
        [declared_field(1, square(0, 200))],
        [declared_plot(1, 1, square(-50)), declared_plot(1, 2, square(100))],
    )

    inherit = reconcile([FIELD], [LEFT, RIGHT], export, {"plot-1-1": LEFT.id})
    fresh = reconcile([FIELD], [LEFT, RIGHT], export, {"plot-1-1": None})

    assert (inherit.plots[0].status, inherit.plots[0].suggested) == (AreaStatus.CHANGED, False)
    assert inherit.blockers == ()
    assert fresh.plots[0].status == AreaStatus.NEW
    assert fresh.removed_plots == (LEFT.id,)


def test_suggestions_can_be_overruled() -> None:
    plan = reconcile([FIELD], [LEFT, RIGHT], same_export(), {"plot-1-1": None})

    assert plan.plots[0].status == AreaStatus.NEW
    assert plan.removed_plots == (LEFT.id,)


def test_an_existing_area_taken_by_the_admin_is_no_longer_suggested_elsewhere() -> None:
    plan = reconcile([FIELD], [LEFT, RIGHT], same_export(), {"plot-1-2": LEFT.id})

    assert plan.plots[1].target == LEFT.id
    assert plan.plots[0].status == AreaStatus.UNDECIDED


def test_a_split_plot_is_suggested_to_neither_part() -> None:
    halves = declaration(
        [declared_field(1, square(0, 200))],
        [
            declared_plot(
                1, 1, {"type": "Polygon", "coordinates": [list(box(0, 0, 50, 100).exterior.coords)]}
            ),
            declared_plot(
                1,
                3,
                {"type": "Polygon", "coordinates": [list(box(50, 0, 100, 100).exterior.coords)]},
            ),
            declared_plot(1, 2, square(100)),
        ],
    )

    plan = reconcile([FIELD], [LEFT, RIGHT], halves, {})

    assert [entry.status for entry in plan.plots] == [
        AreaStatus.UNDECIDED,
        AreaStatus.UNDECIDED,
        AreaStatus.UNCHANGED,
    ]
    assert plan.plots[0].candidates[0].coverage == pytest.approx(1.0)


def test_a_plot_assigned_on_another_field_moves_there() -> None:
    other = existing_field(2, square(1_000, 200))
    export = declaration(
        [declared_field(1, square(0, 200)), declared_field(2, square(1_000, 200))],
        [declared_plot(2, 1, square(0)), declared_plot(1, 2, square(100))],
    )

    plan = reconcile([FIELD, other], [LEFT, RIGHT], export, {})

    assert plan.plots[0].target == LEFT.id
    assert plan.plots[0].changes == (AreaChange.FIELD,)


def test_removing_a_referenced_plot_is_a_blocker() -> None:
    referenced = existing_plot(FIELD, 1, square(0), referenced=True)
    export = declaration([declared_field(1, square(0, 200))], [declared_plot(1, 2, square(100))])

    plan = reconcile([FIELD], [referenced, RIGHT], export, {})

    assert plan.removed_plots == (referenced.id,)
    assert plan.blockers == (AreaUploadBlocker.REMOVES_REFERENCED_AREAS,)


def test_a_locked_year_is_a_blocker() -> None:
    plan = reconcile([FIELD], [LEFT, RIGHT], same_export(), {}, locked=True)

    assert plan.blockers == (AreaUploadBlocker.HARVEST_YEAR_LOCKED,)


def test_geometry_from_elsewhere_counts_as_changed() -> None:
    open_data = existing_plot(FIELD, 1, square(0), from_eama=False)

    plan = reconcile([FIELD], [open_data, RIGHT], same_export(), {})

    assert plan.plots[0].changes == (AreaChange.SOURCE,)


@pytest.mark.parametrize(
    "assignments",
    [
        {"plot-9-9": None},
        {"plot-1-1": uuid.uuid4()},
        {"plot-1-1": FIELD.id},
        {"plot-1-1": LEFT.id, "plot-1-2": LEFT.id},
    ],
    ids=["unknown area", "unknown target", "target of the other kind", "target twice"],
)
def test_invalid_assignments_are_refused(assignments: dict[str, uuid.UUID | None]) -> None:
    with pytest.raises(InvalidAssignmentError):
        reconcile([FIELD], [LEFT, RIGHT], same_export(), assignments)
