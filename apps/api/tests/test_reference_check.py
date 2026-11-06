from typing import Any

from cropstar_api.eama import read_export
from cropstar_api.farmdok.crop_log import read_crop_log
from cropstar_api.farmdok.field_list import read_field_list
from cropstar_api.reference_check import (
    Severity,
    YearState,
    check_crop_log,
    check_eama,
    check_field_list,
)
from tests.eama_export import demo_export
from tests.farmdok_export import DEMO_ENTRIES, crop_log, field_list


def plot(field: int, number: int, area: float, source: str = "eama_export") -> dict[str, Any]:
    return {
        "field": {"number": field},
        "number": number,
        "declared_area_ha": area,
        "provenance": {
            "source": source,
            "borrowed_from_year": 2026 if source == "borrowed" else None,
        },
    }


DEMO_PLOTS = [plot(1, 1, 4.8094), plot(1, 2, 0.441), plot(2, 1, 2.7669), plot(2, 2, 0.6865)]


def severities(findings: list[Any]) -> list[Severity]:
    return [f.severity for f in findings]


def test_a_year_matching_its_eama_export_passes() -> None:
    declaration = read_export(demo_export(2026).items())

    findings = check_eama(declaration, YearState(DEMO_PLOTS, []))

    assert severities(findings) == [Severity.OK, Severity.OK]
    assert "4 Schläge, 8.7038 ha" in findings[0].message


def test_missing_extra_and_different_plots_are_mismatches() -> None:
    declaration = read_export(demo_export(2026).items())
    plots = [plot(1, 1, 4.8), plot(1, 2, 0.441), plot(2, 1, 2.7669), plot(3, 1, 1.0)]

    messages = [f.message for f in check_eama(declaration, YearState(plots, []))]

    assert messages[:3] == [
        "Im eAMA-Export, nicht in Cropstar: 2.2",
        "In Cropstar, nicht im eAMA-Export: 3.1",
        "Fläche weicht ab: 1.1 (4.8094 statt 4.8000 ha)",
    ]


def test_a_field_list_year_has_provisional_geometry() -> None:
    plots = [
        {**p, "provenance": {"source": "borrowed", "borrowed_from_year": 2026}} for p in DEMO_PLOTS
    ]
    plots[-1]["provenance"] = {"source": "none", "borrowed_from_year": None}

    findings = check_field_list(read_field_list(field_list()), YearState(plots, []))

    assert [(f.severity, f.message) for f in findings[1:]] == [
        (Severity.OK, "3 Schläge mit vorläufiger Geometrie aus 2026"),
        (Severity.CHECK, "Ohne Geometrie (nichts zu übernehmen): 2.2"),
    ]


def task(title: str, day: str, *fields: int) -> dict[str, Any]:
    return {
        "title": title,
        "imported": {"kind": "farmdok_crop_log"},
        "operations": [{"performed_on": day, "plot": {"field_number": f}} for f in fields],
    }


def test_every_log_entry_is_found_as_an_imported_task_or_listed() -> None:
    log = read_crop_log(crop_log())
    tasks = [
        task("Wirtschaftsdünger Mist", "2024-08-28", 1),
        task("Scheibenegge", "2024-09-02", 1),
        task("Aussaat Hauptkultur", "2024-10-02", 1),
        task("Striegeln", "2025-03-25", 1),
    ]

    findings = check_crop_log(log, YearState([], tasks))

    assert findings[0].message == "4 von 5 Journaleinträgen als erledigte Aufgaben importiert"
    assert findings[1].severity is Severity.CHECK
    assert "Zeile 11, 20.07.2025 Mähdrusch" in findings[1].message
    assert len(DEMO_ENTRIES) == 5


def test_tasks_without_an_entry_and_a_missing_import_are_mismatches() -> None:
    log = read_crop_log(crop_log(DEMO_ENTRIES[:1]))

    extra = check_crop_log(
        log,
        YearState(
            [], [task("Wirtschaftsdünger Mist", "2024-08-28", 1), task("X", "2025-01-01", 1)]
        ),
    )
    none = check_crop_log(
        log, YearState([], [{"title": "Zaun", "imported": None, "operations": []}])
    )

    assert extra[-1].message == "1 importierte Aufgaben ohne passenden Journaleintrag"
    assert [f.severity for f in none] == [Severity.MISMATCH]


def square(lon: float, lat: float, metres: float) -> dict[str, Any]:
    """A square of about `metres` side length, in WGS84."""
    d_lat = metres / 110_574
    d_lon = metres / (111_320 * 0.68)
    ring = [
        [lon, lat],
        [lon + d_lon, lat],
        [lon + d_lon, lat + d_lat],
        [lon, lat + d_lat],
        [lon, lat],
    ]
    return {"type": "MultiPolygon", "coordinates": [[ring]]}


def test_borrowed_geometry_of_the_wrong_size_is_flagged() -> None:
    # 100 m squares: 1 ha. Plot 1.2 declares 0.441 ha but got a 1 ha geometry.
    plots = [
        {**p, "provenance": {"source": "borrowed", "borrowed_from_year": 2026}} for p in DEMO_PLOTS
    ]
    for p in plots:
        p["geometry"] = square(16.4, 48.7, 100)
    plots[0]["declared_area_ha"] = 1.0

    findings = check_field_list(read_field_list(field_list()), YearState(plots, []))

    misfit = next(f for f in findings if "Größe" in f.message)
    assert misfit.severity is Severity.CHECK
    assert misfit.message.startswith("Vorläufige Geometrie passt in der Größe nicht: 1.2 (0.44 ha")
    assert "1.1 (" not in misfit.message
