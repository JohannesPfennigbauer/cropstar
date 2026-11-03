from decimal import Decimal

import pytest

from cropstar_api import eama
from cropstar_api.eama import EamaExportError, Problem, ProblemCode, read_export
from tests.eama_export import (
    WGS84_PRJ,
    demo_export,
    demo_rows,
    fields_set,
    plots_set,
    zipped,
)


def problems_of(files: dict[str, bytes]) -> tuple[Problem, ...]:
    with pytest.raises(EamaExportError) as raised:
        read_export(files.items())
    return raised.value.problems


def test_reads_fields_and_plots_of_the_harvest_year() -> None:
    declaration = read_export(demo_export(2026).items())

    assert declaration.harvest_year == 2026
    assert [(f.number, f.name) for f in declaration.fields] == [
        (1, "Kellerberg"),
        (2, "Am Graben"),
    ]
    assert [(p.field_number, p.number, p.land_use_name) for p in declaration.plots] == [
        (1, 1, "WINTERROGGEN"),
        (1, 2, "GRÜNBRACHE"),
        (2, 1, "SONNENBLUMEN"),
        (2, 2, "SOMMERGERSTE"),
    ]
    first = declaration.fields[0]
    assert (first.land_use_code, first.land_use_name) == ("A", "ACKERLAND")
    assert first.declared_area_ha == Decimal("5.2504")


def test_plot_declared_area_is_the_gross_area() -> None:
    declaration = read_export(demo_export().items())

    assert declaration.plots[0].declared_area_ha == Decimal("4.8094")


def test_geometry_stays_in_austria_lambert_and_keeps_holes() -> None:
    field = read_export(demo_export().items()).fields[0]

    assert field.geometry["type"] == "MultiPolygon"
    [polygon] = field.geometry["coordinates"]
    assert len(polygon) == 2  # outer ring and one hole
    x, y = polygon[0][0]
    assert 100_000 < x < 700_000
    assert 250_000 < y < 600_000


def test_harvest_year_comes_from_the_export() -> None:
    assert read_export(demo_export(2025).items()).harvest_year == 2025


def test_file_names_do_not_matter() -> None:
    fields, plots = demo_rows()
    files = fields_set(fields, stem="a") | plots_set(plots, stem="b")

    declaration = read_export(files.items())

    assert (len(declaration.fields), len(declaration.plots)) == (2, 4)


def test_loose_files_and_archives_combine() -> None:
    fields, plots = demo_rows()
    files = {
        "fields.zip": zipped(fields_set(fields), folder="export/FS/"),
        **plots_set(plots),
    }

    declaration = read_export(files.items())

    assert (len(declaration.fields), len(declaration.plots)) == (2, 4)


def test_one_archive_can_hold_both_sets_and_unrelated_files() -> None:
    archive = zipped({**demo_export(), "Export.log": b"done", "readme.txt": b"hi"})

    declaration = read_export([("Download.ZIP", archive)])

    assert (len(declaration.fields), len(declaration.plots)) == (2, 4)


def test_paths_inside_archives_are_reduced_to_file_names() -> None:
    archive = zipped(demo_export(), folder="../../outside/")

    declaration = read_export([("export.zip", archive)])

    assert len(declaration.plots) == 4


def test_missing_components_are_reported_by_name() -> None:
    files = demo_export()
    shx = next(name for name in files if "FLSL" in name and name.endswith(".shx"))
    del files[shx]

    assert problems_of(files) == (Problem(ProblemCode.MISSING_COMPONENT, file=shx),)


def test_a_missing_set_is_reported() -> None:
    fields, _ = demo_rows()

    assert problems_of(fields_set(fields)) == (Problem(ProblemCode.MISSING_SET, detail="plots"),)


def test_a_second_set_of_the_same_kind_is_reported() -> None:
    _, plots = demo_rows()
    files = demo_export() | plots_set(plots, stem="other")

    [problem] = problems_of(files)

    assert problem.code is ProblemCode.DUPLICATE_SET


def test_a_wrong_projection_is_rejected() -> None:
    fields, plots = demo_rows()
    files = fields_set(fields, stem="fs", prj=WGS84_PRJ) | plots_set(plots)

    assert problems_of(files) == (Problem(ProblemCode.WRONG_PROJECTION, file="fs.shp"),)


def test_conflicting_harvest_years_are_rejected() -> None:
    fields, plots = demo_rows()
    files = fields_set(fields, year=2025) | plots_set(plots, year=2026)

    assert problems_of(files) == (Problem(ProblemCode.MIXED_HARVEST_YEARS, detail="2025, 2026"),)


def test_plots_must_belong_to_a_field_of_the_export() -> None:
    fields, plots = demo_rows()
    files = fields_set(fields[:1]) | plots_set(plots)

    problems = problems_of(files)

    assert {(p.code, p.field_number) for p in problems} == {(ProblemCode.PLOT_WITHOUT_FIELD, 2)}


def test_text_follows_a_declared_code_page() -> None:
    fields, plots = demo_rows()
    files = fields_set(fields) | plots_set(plots, stem="sl", encoding="utf-8")
    files["sl.cpg"] = b"UTF-8"

    declaration = read_export(files.items())

    assert declaration.plots[1].land_use_name == "GRÜNBRACHE"


def test_nothing_to_read() -> None:
    assert problems_of({"notes.txt": b"x"}) == (Problem(ProblemCode.NO_FILES),)


def test_broken_archives_are_reported() -> None:
    assert problems_of({"export.zip": b"not a zip"}) == (
        Problem(ProblemCode.UNREADABLE_ARCHIVE, file="export.zip"),
    )


def test_unpacking_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eama, "MAX_UNPACKED_BYTES", 1_000)

    assert problems_of({"export.zip": zipped(demo_export())}) == (Problem(ProblemCode.TOO_LARGE),)
