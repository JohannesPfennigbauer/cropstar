from decimal import Decimal

import pytest

from cropstar_api.farmdok.field_list import read_field_list
from cropstar_api.farmdok.field_list_plan import (
    GeometryMatch,
    InvalidCropAssignmentError,
    Reference,
    nearest_year,
    plan,
)
from cropstar_api.farmdok.report import FarmdokError, ProblemCode
from tests.farmdok_export import DEMO_ROWS, Row, field_list


def test_the_report_is_read_without_header_sum_and_footnote_rows() -> None:
    result = read_field_list(field_list(year=2024))

    assert (result.harvest_year, result.farm_number) == (2024, "9999999")
    assert [(r.field_number, r.plot_number, r.crop) for r in result.rows] == [
        (1, 1, "Winterroggen"),
        (1, 2, "Grünbrache"),
        (2, 1, "Sonnenblumen"),
        (2, 2, "Sommerbraugerste"),
    ]
    first = result.rows[0]
    assert (first.field_name, first.field_land_use, first.field_area_ha, first.plot_area_ha) == (
        "Kellerberg",
        "Ackerland",
        None,
        Decimal("4.8094"),
    )


def test_field_numbers_sort_as_text_in_farmdok_but_are_read_as_integers() -> None:
    rows = (Row(10, "Zehn", 1, "Grünbrache", 1.0), Row(2, "Zwei", 1, "Grünbrache", 1.0))

    result = read_field_list(field_list(rows))

    assert sorted(r.field_number for r in result.rows) == [2, 10]


@pytest.mark.parametrize(
    ("content", "code"),
    [(b"not a spreadsheet", ProblemCode.UNREADABLE_FILE), (field_list(()), ProblemCode.EMPTY)],
)
def test_unusable_files_are_refused(content: bytes, code: ProblemCode) -> None:
    with pytest.raises(FarmdokError) as error:
        read_field_list(content)

    assert [p.code for p in error.value.problems] == [code]


def test_duplicate_plots_are_reported_with_their_row() -> None:
    rows = (*DEMO_ROWS, Row(1, "Kellerberg", 1, "Winterroggen", 1.0))

    with pytest.raises(FarmdokError) as error:
        read_field_list(field_list(rows))

    assert [(p.code, p.detail) for p in error.value.problems] == [
        (ProblemCode.DUPLICATE_PLOT, "1.1")
    ]


REFERENCE = Reference(
    2026,
    fields={1: "field-1", 2: "field-2"},
    plots={(1, 1): "plot-1-1", (2, 1): "plot-2-1"},
)

NO_REFERENCE: Reference[str] | None = None


def test_geometry_is_borrowed_by_number_falling_back_to_the_field() -> None:
    rows = (*DEMO_ROWS, Row(3, "Neu", 1, "Grünbrache", 1.0))

    result = plan(read_field_list(field_list(rows)), REFERENCE, {})

    assert result.reference_year == 2026
    assert [(p.field_number, p.number, p.geometry, p.match) for p in result.plots] == [
        (1, 1, "plot-1-1", GeometryMatch.PLOT),
        (1, 2, "field-1", GeometryMatch.FIELD),
        (2, 1, "plot-2-1", GeometryMatch.PLOT),
        (2, 2, "field-2", GeometryMatch.FIELD),
        (3, 1, None, GeometryMatch.NONE),
    ]
    assert [(f.number, f.geometry) for f in result.fields] == [
        (1, "field-1"),
        (2, "field-2"),
        (3, None),
    ]


def test_without_a_reference_nothing_has_geometry() -> None:
    result = plan(read_field_list(field_list()), NO_REFERENCE, {})

    assert {p.match for p in result.plots} == {GeometryMatch.NONE}


def test_fields_take_the_size_of_their_plots_when_farmdok_has_none() -> None:
    result = plan(read_field_list(field_list()), NO_REFERENCE, {})

    assert result.fields[0].declared_area_ha == Decimal("4.8094") + Decimal("0.441")
    assert (result.fields[0].land_use_code, result.fields[0].land_use_name) == ("A", "ACKERLAND")


def test_crops_map_to_ama_land_uses_and_unknown_ones_wait_for_the_admin() -> None:
    rows = (*DEMO_ROWS, Row(3, "Rain", 1, "Sonstige Grünlandfläche", 0.1))
    field_list_ = read_field_list(field_list(rows))

    open_ = plan(field_list_, NO_REFERENCE, {})
    assigned = plan(field_list_, NO_REFERENCE, {"Sonstige Grünlandfläche": "361"})

    lands = {p.crop: p.land_use for p in open_.plots}
    assert lands["Winterroggen"] == ("142", "WINTERROGGEN")
    assert lands["Sommerbraugerste"] == ("111", "SOMMERGERSTE")
    assert lands["Sonstige Grünlandfläche"] is None
    assert [(c.name, c.plot_count) for c in open_.unknown_crops] == [("Sonstige Grünlandfläche", 1)]
    assert assigned.unknown_crops == ()
    assert assigned.plots[-1].land_use is not None
    assert assigned.plots[-1].land_use[0] == "361"


@pytest.mark.parametrize("assignment", [{"Hafer": "142"}, {"Winterroggen": "000"}])
def test_invalid_crop_assignments_are_refused(assignment: dict[str, str]) -> None:
    with pytest.raises(InvalidCropAssignmentError):
        plan(read_field_list(field_list()), NO_REFERENCE, assignment)


def test_the_nearest_other_year_is_the_default_reference() -> None:
    assert nearest_year(2024, {2026, 2022}) == 2026
    assert nearest_year(2023, {2023, 2026}) == 2026
    assert nearest_year(2023, {2023}) is None


def test_a_renumbered_plot_is_found_by_its_area_on_the_same_field() -> None:
    # eAMA renumbered Field 8: farmdok's 8.2 (tiny) is eAMA's 8.4, farmdok's 8.3 is eAMA's 8.2.
    rows = (
        Row(8, "Acht", 1, "Grünbrache", 0.3343),
        Row(8, "Acht", 2, "sonstige Ackerfläche", 0.0201),
        Row(8, "Acht", 3, "Ölkürbis", 6.2342),
    )
    reference = Reference(
        2026,
        fields={8: "field-8"},
        plots={(8, 1): "plot-8-1", (8, 2): "plot-8-2", (8, 4): "plot-8-4"},
        plot_areas={
            (8, 1): Decimal("0.3343"),
            (8, 2): Decimal("6.2347"),
            # 0.0197 against 0.0201 is 2 % off, but only 4 m².
            (8, 4): Decimal("0.0197"),
        },
    )

    result = plan(read_field_list(field_list(rows)), reference, {})

    assert [(p.number, p.geometry, p.match) for p in result.plots] == [
        (1, "plot-8-1", GeometryMatch.PLOT),
        (2, "plot-8-4", GeometryMatch.AREA),
        (3, "plot-8-2", GeometryMatch.AREA),
    ]


def test_without_a_plausible_plot_the_field_geometry_is_used() -> None:
    rows = (Row(8, "Acht", 2, "Ölkürbis", 3.0),)
    reference = Reference(
        2026, fields={8: "field-8"}, plots={(8, 2): "plot-8-2"}, plot_areas={(8, 2): Decimal("6.2")}
    )

    result = plan(read_field_list(field_list(rows)), reference, {})

    assert (result.plots[0].geometry, result.plots[0].match) == ("field-8", GeometryMatch.FIELD)
