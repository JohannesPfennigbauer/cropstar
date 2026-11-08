import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from cropstar_api import plot_lineage
from cropstar_api.models import AreaSource, Field, Plot
from tests.farm_fixtures import Areas, Farm


def rectangle(x: float, y: float, width: float, height: float = 100) -> str:
    """A rectangle in the AMA CRS, as EWKT."""
    ring = f"{x} {y}, {x + width} {y}, {x + width} {y + height}, {x} {y + height}, {x} {y}"
    return f"SRID=31287;MULTIPOLYGON((({ring})))"


def add_year(db: Session, farm: Farm, year: int, plots: list[tuple[str, str, str]]) -> list[str]:
    """One Field for the year with Plots given as (land use code, name, geometry)."""
    field = Field(
        farm_id=farm.id,
        harvest_year=year,
        number=1,
        name="Feld 1",
        land_use_code="A",
        land_use_name="ACKERLAND",
        declared_area_ha=1,
        geometry=rectangle(600_200, 502_027, 100),
        geometry_source=AreaSource.EAMA_EXPORT,
        imported_at=datetime.now(UTC),
    )
    db.add(field)
    db.flush()
    created = [
        Plot(
            field_id=field.id,
            number=number,
            land_use_code=code,
            land_use_name=name,
            declared_area_ha=0.5,
            geometry=geometry,
            geometry_source=AreaSource.EAMA_EXPORT,
            imported_at=datetime.now(UTC),
        )
        for number, (code, name, geometry) in enumerate(plots, start=1)
    ]
    db.add_all(created)
    plot_lineage.relink(db, uuid.UUID(farm.id), year)
    db.commit()
    return [str(p.id) for p in created]


def lineage(farm: Farm, plot_id: str) -> list[tuple[int, int, str, str, float]]:
    response = farm.advisor.client.get(f"/api/farms/{farm.id}/plots/{plot_id}/lineage")
    assert response.status_code == 200, response.text
    return [
        (
            p["harvest_year"],
            p["plot_number"],
            p["land_use_name"],
            p["land_use_category"],
            p["overlap"],
        )
        for p in response.json()
    ]


def test_the_plot_of_the_year_before_on_the_same_ground_is_the_predecessor(
    farm: Farm, areas: Areas
) -> None:
    assert lineage(farm, areas.plot_2027_a) == [(2026, 1, "SONNENBLUMEN", "oilseeds", 0.99)]
    assert lineage(farm, areas.plot_2026) == []


def test_a_merger_has_several_predecessors_and_the_lineage_reaches_back(
    farm: Farm, areas: Areas, db: Session
) -> None:
    # 2025: the ground was two Plots, each half of what became one Plot in 2026.
    add_year(
        db,
        farm,
        2025,
        [
            ("142", "WINTERROGGEN", rectangle(600_200, 502_026, 50)),
            ("401", "SOMMERGERSTE", rectangle(600_250, 502_026, 50)),
        ],
    )

    years = lineage(farm, areas.plot_2027_a)

    assert [(year, number, name) for year, number, name, _, _ in years] == [
        (2026, 1, "SONNENBLUMEN"),
        (2025, 1, "WINTERROGGEN"),
        (2025, 2, "SOMMERGERSTE"),
    ]
    assert [round(overlap, 1) for *_, overlap in years] == [1.0, 0.5, 0.5]


def test_a_split_keeps_the_larger_plot_of_the_year_before(
    farm: Farm, areas: Areas, db: Session
) -> None:
    [whole] = add_year(db, farm, 2030, [("307", "SONNENBLUMEN", rectangle(600_200, 502_027, 100))])
    halves = add_year(
        db,
        farm,
        2031,
        [
            ("142", "WINTERROGGEN", rectangle(600_200, 502_027, 50)),
            ("401", "SOMMERGERSTE", rectangle(600_250, 502_027, 50)),
        ],
    )

    for half in halves:
        year_before = [p for p in lineage(farm, half) if p[0] == 2030]
        assert year_before == [(2030, 1, "SONNENBLUMEN", "oilseeds", 1.0)]
    # The 2030 Plot in turn lies on the fixture's 2027 ground.
    assert {p[0] for p in lineage(farm, whole)} == {2027, 2026}


def test_little_shared_ground_is_no_predecessor(farm: Farm, db: Session) -> None:
    add_year(db, farm, 2040, [("307", "SONNENBLUMEN", rectangle(600_200, 502_027, 100))])
    [shifted] = add_year(
        db, farm, 2041, [("142", "WINTERROGGEN", rectangle(600_270, 502_027, 100))]
    )

    assert lineage(farm, shifted) == []


def test_lineage_stays_within_the_farm(farm: Farm, areas: Areas) -> None:
    response = farm.stranger.client.get(f"/api/farms/{farm.id}/plots/{areas.plot_2027_a}/lineage")
    assert response.status_code in (403, 404)
    assert lineage(farm, areas.elsewhere_plot) == []
