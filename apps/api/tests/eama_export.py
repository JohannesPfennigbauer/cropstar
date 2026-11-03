"""Synthetic eAMA area exports for tests, built from the public INVEKOS demo areas.

Never use a real farm's export in tests: it is commercially sensitive. Run as a module to
write a demo export for the end-to-end tests:

    uv run python -m tests.eama_export <directory>    (from apps/api)
"""

import io
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import shapefile

from cropstar_api.seed import load_fixture

AUSTRIA_LAMBERT_PRJ = (
    'PROJCS["MGI_Austria_Lambert",GEOGCS["GCS_MGI",DATUM["D_MGI",'
    'SPHEROID["Bessel_1841",6377397.155,299.1528128]],PRIMEM["Greenwich",0.0],'
    'UNIT["Degree",0.0174532925199433]],PROJECTION["Lambert_Conformal_Conic"],'
    'PARAMETER["False_Easting",400000.0],PARAMETER["False_Northing",400000.0],'
    'PARAMETER["Central_Meridian",13.33333333333333],PARAMETER["Standard_Parallel_1",46.0],'
    'PARAMETER["Standard_Parallel_2",49.0],PARAMETER["Latitude_Of_Origin",47.5],'
    'UNIT["Meter",1.0]]'
)
WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)
FIELDS_STEM = "9999999MFA{year}ERFFL_FS_{year}1026094443"
PLOTS_STEM = "9999999MFA{year}ERFFL_FLSL_23_{year}1026094500"

Rings = list[list[list[float]]]


@dataclass(frozen=True)
class FieldRow:
    number: int
    name: str
    land_use_code: str
    land_use_name: str
    area_ha: float
    rings: Rings


@dataclass(frozen=True)
class PlotRow:
    field_number: int
    number: int
    land_use_code: str
    land_use_name: str
    area_ha: float
    rings: Rings


def demo_rows() -> tuple[list[FieldRow], list[PlotRow]]:
    """The demo Farm's two Fields and four Plots, with names and umlauts."""
    features = load_fixture()["features"]
    numbers = {
        f["properties"]["fs_kennung"]: f["properties"]["number"]
        for f in features
        if f["properties"]["kind"] == "field"
    }
    fields, plots = [], []
    for feature in features:
        p = feature["properties"]
        rings = feature["geometry"]["coordinates"]
        if p["kind"] == "field":
            fields.append(
                FieldRow(
                    p["number"],
                    p["name"],
                    p["fnar_code"],
                    p["fnar_bezeichnung"],
                    p["fs_flaeche_ha"],
                    rings,
                )
            )
        else:
            plots.append(
                PlotRow(
                    numbers[p["fs_kennung"]],
                    p["number"],
                    p["snar_code"],
                    p["snar_bezeichnung"],
                    p["sl_flaeche_brutto_ha"],
                    rings,
                )
            )
    return fields, plots


def fields_set(
    rows: list[FieldRow],
    *,
    year: int = 2026,
    stem: str | None = None,
    prj: str = AUSTRIA_LAMBERT_PRJ,
) -> dict[str, bytes]:
    """The Field set, with eAMA's attribute names and types."""

    def define(writer: shapefile.Writer) -> None:
        writer.field("HBNR", "C", 40)
        writer.field("TBNR", "F", 24, 5)
        writer.field("BBK", "F", 24, 5)
        writer.field("FART", "C", 255)
        writer.field("FSNR", "F", 24, 5)
        writer.field("FSNAME", "C", 240)
        writer.field("FNAR_CODE", "C", 30)
        writer.field("FNAR", "C", 255)
        writer.field("FLAECHE", "F", 24, 5)

    records = [
        (
            [
                "9999999",
                0.0,
                0.0,
                f"MFA{year}",
                float(r.number),
                r.name,
                r.land_use_code,
                r.land_use_name,
                r.area_ha,
            ],
            r.rings,
        )
        for r in rows
    ]
    return _shapefile_set(stem or FIELDS_STEM.format(year=year), prj, define, records)


def plots_set(
    rows: list[PlotRow],
    *,
    year: int = 2026,
    stem: str | None = None,
    prj: str = AUSTRIA_LAMBERT_PRJ,
    encoding: str = "cp1252",
) -> dict[str, bytes]:
    """The Plot set, with eAMA's attribute names and types."""

    def define(writer: shapefile.Writer) -> None:
        writer.field("HBNR", "F", 24, 5)
        writer.field("FART", "C", 255)
        writer.field("FSNR", "F", 24, 5)
        writer.field("FSNAME", "C", 240)
        writer.field("SLNR", "N", 10, 0)
        writer.field("SNAR_CODE", "C", 30)
        writer.field("SNAR", "C", 255)
        writer.field("FLAECHE_BR", "F", 24, 5)
        writer.field("FLAECHE_NE", "F", 24, 5)

    records = [
        (
            [
                9999999.0,
                f"MFA{year}",
                float(r.field_number),
                "",
                r.number,
                r.land_use_code,
                r.land_use_name,
                r.area_ha,
                r.area_ha * 0.98,
            ],
            r.rings,
        )
        for r in rows
    ]
    return _shapefile_set(stem or PLOTS_STEM.format(year=year), prj, define, records, encoding)


def demo_export(year: int = 2026) -> dict[str, bytes]:
    """Both sets, as eAMA names them."""
    fields, plots = demo_rows()
    return fields_set(fields, year=year) | plots_set(plots, year=year)


def zipped(files: dict[str, bytes], folder: str = "") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(f"{folder}{name}", content)
    return buffer.getvalue()


def _shapefile_set(
    stem: str,
    prj: str,
    define: Any,
    records: list[tuple[list[Any], Rings]],
    encoding: str = "cp1252",
) -> dict[str, bytes]:
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    writer = shapefile.Writer(
        shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON, encoding=encoding
    )
    define(writer)
    for values, rings in records:
        writer.poly(_shapefile_rings(rings))
        writer.record(*values)
    writer.close()
    return {
        f"{stem}.shp": shp.getvalue(),
        f"{stem}.shx": shx.getvalue(),
        f"{stem}.dbf": dbf.getvalue(),
        f"{stem}.prj": prj.encode("ascii"),
    }


def _shapefile_rings(rings: Rings) -> list[Any]:
    """Shapefiles want the outer ring clockwise and holes counter-clockwise."""
    oriented = []
    for index, ring in enumerate(rings):
        clockwise = shapefile.is_cw(ring)
        wanted = index == 0
        oriented.append(ring if clockwise == wanted else list(reversed(ring)))
    return oriented


if __name__ == "__main__":
    target = Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    for name, content in demo_export().items():
        (target / name).write_bytes(content)
