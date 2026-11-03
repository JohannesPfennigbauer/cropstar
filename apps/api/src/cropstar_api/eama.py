"""Reader for the area export of eAMA, the online application of Agrarmarkt Austria.

eAMA exports a Harvest Year's areas as two ESRI shapefile sets: the Fields (Feldstücke) and
the Plots (Schläge). Each set is four files (`.shp`, `.shx`, `.dbf`, `.prj`), and farmers
upload them loose or zipped, under whatever names their browser gave them. So the sets are
recognised by their attributes: Plots carry a Plot number (`SLNR`), Fields do not.

Pure: file contents in, an `AreaDeclaration` out, or `EamaExportError` with every problem
found. Nothing is written anywhere; archives are unpacked in memory.
"""

import codecs
import enum
import io
import math
import re
import struct
import zipfile
import zlib
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Any

import shapefile

# One farm's export is a few hundred kB; these only stop abuse.
MAX_UNPACKED_BYTES = 50 * 1024 * 1024
MAX_FILES = 200

_REQUIRED_COMPONENTS = (".shp", ".shx", ".dbf", ".prj")
_ACCEPTED_EXTENSIONS = frozenset({*_REQUIRED_COMPONENTS, ".cpg"})
# eAMA writes Windows-1252 text and no `.cpg` file saying so.
_DEFAULT_ENCODING = "cp1252"
_FIELD_ATTRIBUTES = ("FART", "FSNR", "FSNAME", "FNAR_CODE", "FNAR", "FLAECHE")
_PLOT_ATTRIBUTES = ("FART", "FSNR", "SLNR", "SNAR_CODE", "SNAR", "FLAECHE_BR")
# `MFA2026`: the multiple application (Mehrfachantrag) for Harvest Year 2026.
_APPLICATION_TYPE = re.compile(r"(\d{4})\s*$")


class ProblemCode(enum.StrEnum):
    NO_FILES = "no_files"
    TOO_LARGE = "too_large"
    UNREADABLE_ARCHIVE = "unreadable_archive"
    CONFLICTING_FILES = "conflicting_files"
    MISSING_COMPONENT = "missing_component"
    UNREADABLE_SHAPEFILE = "unreadable_shapefile"
    WRONG_PROJECTION = "wrong_projection"
    UNKNOWN_SET = "unknown_set"
    MISSING_ATTRIBUTE = "missing_attribute"
    NOT_POLYGONS = "not_polygons"
    DUPLICATE_SET = "duplicate_set"
    MISSING_SET = "missing_set"
    MISSING_HARVEST_YEAR = "missing_harvest_year"
    MIXED_HARVEST_YEARS = "mixed_harvest_years"
    INVALID_RECORD = "invalid_record"
    DUPLICATE_AREA = "duplicate_area"
    PLOT_WITHOUT_FIELD = "plot_without_field"


class SetKind(enum.StrEnum):
    FIELDS = "fields"
    PLOTS = "plots"


@dataclass(frozen=True)
class Problem:
    code: ProblemCode
    # The file, or the shapefile set by the name of its `.shp`, the problem is about.
    file: str | None = None
    field_number: int | None = None
    plot_number: int | None = None
    # A value to show, such as the missing attribute or the conflicting years.
    detail: str | None = None


class EamaExportError(Exception):
    def __init__(self, problems: Iterable[Problem]) -> None:
        self.problems = tuple(problems)
        super().__init__(", ".join(problem.code for problem in self.problems))


@dataclass(frozen=True)
class DeclaredField:
    number: int
    name: str | None
    land_use_code: str
    land_use_name: str
    declared_area_ha: Decimal
    # GeoJSON MultiPolygon in EPSG:31287 (MGI / Austria Lambert), as exported.
    geometry: dict[str, Any]


@dataclass(frozen=True)
class DeclaredPlot:
    field_number: int
    number: int
    land_use_code: str
    land_use_name: str
    # The gross area: what the farmer works, including landscape elements on the Plot.
    declared_area_ha: Decimal
    geometry: dict[str, Any]


@dataclass(frozen=True)
class AreaDeclaration:
    """The Fields and Plots a Farm declared to AMA for one Harvest Year."""

    harvest_year: int
    fields: tuple[DeclaredField, ...]
    plots: tuple[DeclaredPlot, ...]


def read_export(files: Iterable[tuple[str, bytes]]) -> AreaDeclaration:
    """Read an eAMA area export from `(file name, content)` pairs: shapefile components and
    ZIP archives containing them, in any combination."""
    problems: list[Problem] = []
    unpacked = _unpack(files, problems)
    if problems:
        raise EamaExportError(problems)
    if not unpacked:
        raise EamaExportError([Problem(ProblemCode.NO_FILES)])

    sets: dict[SetKind, list[_ShapefileSet]] = defaultdict(list)
    for stem, components in _group_by_stem(unpacked).items():
        read = _read_set(stem, components, problems)
        if read is not None:
            sets[read.kind].append(read)
    for kind in SetKind:
        if len(sets[kind]) > 1:
            names = ", ".join(sorted(s.name for s in sets[kind]))
            problems.append(Problem(ProblemCode.DUPLICATE_SET, detail=names))
        elif not sets[kind] and not problems:
            problems.append(Problem(ProblemCode.MISSING_SET, detail=kind.value))
    if problems:
        raise EamaExportError(problems)

    field_set, plot_set = sets[SetKind.FIELDS][0], sets[SetKind.PLOTS][0]
    fields = _fields(field_set, problems)
    plots = _plots(plot_set, problems)
    harvest_year = _harvest_year([field_set, plot_set], problems)
    _check_references(fields, plots, problems)
    if problems or harvest_year is None:
        raise EamaExportError(problems)
    return AreaDeclaration(
        harvest_year=harvest_year,
        fields=tuple(sorted(fields, key=lambda f: f.number)),
        plots=tuple(sorted(plots, key=lambda p: (p.field_number, p.number))),
    )


# --- Unpacking ---------------------------------------------------------------------------


def _unpack(files: Iterable[tuple[str, bytes]], problems: list[Problem]) -> dict[str, bytes]:
    """Every accepted file by its bare name; directories inside archives are dropped, so
    nothing can point outside the upload."""
    unpacked: dict[str, bytes] = {}
    budget = MAX_UNPACKED_BYTES

    def add(name: str, content: bytes) -> None:
        nonlocal budget
        if len(unpacked) >= MAX_FILES or len(content) > budget:
            raise _TooLargeError
        budget -= len(content)
        if name in unpacked and unpacked[name] != content:
            problems.append(Problem(ProblemCode.CONFLICTING_FILES, file=name))
        unpacked[name] = content

    try:
        for name, content in files:
            bare = _bare_name(name)
            if _extension(bare) == ".zip":
                _unpack_archive(bare, content, add, problems)
            elif _extension(bare) in _ACCEPTED_EXTENSIONS:
                add(bare, content)
    except _TooLargeError:
        problems.append(Problem(ProblemCode.TOO_LARGE))
    return unpacked


class _TooLargeError(Exception):
    pass


def _unpack_archive(
    name: str, content: bytes, add: Callable[[str, bytes], None], problems: list[Problem]
) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for info in archive.infolist():
                bare = _bare_name(info.filename)
                if info.is_dir() or _extension(bare) not in _ACCEPTED_EXTENSIONS:
                    continue
                if info.file_size > MAX_UNPACKED_BYTES:
                    raise _TooLargeError
                with archive.open(info) as member:
                    # Bounded even if the archive lies about the size.
                    add(bare, member.read(MAX_UNPACKED_BYTES + 1))
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error):
        # RuntimeError: encrypted; NotImplementedError: unsupported compression.
        problems.append(Problem(ProblemCode.UNREADABLE_ARCHIVE, file=name))


def _bare_name(name: str) -> str:
    return PurePosixPath(name.replace("\\", "/")).name


def _extension(name: str) -> str:
    return PurePosixPath(name).suffix.lower()


def _group_by_stem(files: dict[str, bytes]) -> dict[str, dict[str, bytes]]:
    groups: dict[str, dict[str, bytes]] = defaultdict(dict)
    for name, content in files.items():
        path = PurePosixPath(name)
        groups[path.stem][path.suffix.lower()] = content
    return groups


# --- One shapefile set -------------------------------------------------------------------


@dataclass(frozen=True)
class _ShapefileSet:
    name: str
    kind: SetKind
    # Attributes by upper-case name, and the geometry if it is a polygon, per record.
    records: tuple[tuple[dict[str, Any], dict[str, Any] | None], ...]


def _read_set(
    stem: str, components: dict[str, bytes], problems: list[Problem]
) -> _ShapefileSet | None:
    missing = [ext for ext in _REQUIRED_COMPONENTS if ext not in components]
    if missing:
        problems.extend(
            Problem(ProblemCode.MISSING_COMPONENT, file=f"{stem}{ext}") for ext in missing
        )
        return None
    name = f"{stem}.shp"
    if not _is_austria_lambert(components[".prj"]):
        problems.append(Problem(ProblemCode.WRONG_PROJECTION, file=name))
        return None
    try:
        reader = shapefile.Reader(
            shp=io.BytesIO(components[".shp"]),
            shx=io.BytesIO(components[".shx"]),
            dbf=io.BytesIO(components[".dbf"]),
            encoding=_encoding(components.get(".cpg")),
        )
        attributes = {f.name.upper() for f in reader.fields if f.name != "DeletionFlag"}
        if "SLNR" in attributes:
            kind, required = SetKind.PLOTS, _PLOT_ATTRIBUTES
        elif "FSNR" in attributes:
            kind, required = SetKind.FIELDS, _FIELD_ATTRIBUTES
        else:
            problems.append(Problem(ProblemCode.UNKNOWN_SET, file=name))
            return None
        absent = [a for a in required if a not in attributes]
        if absent:
            problems.append(
                Problem(ProblemCode.MISSING_ATTRIBUTE, file=name, detail=", ".join(absent))
            )
            return None
        if reader.shapeType != shapefile.POLYGON:
            problems.append(Problem(ProblemCode.NOT_POLYGONS, file=name))
            return None
        records = tuple(
            (
                {key.upper(): value for key, value in item.record.as_dict().items()},
                _multipolygon(item.shape),
            )
            for item in reader.iterShapeRecords()
        )
    except (shapefile.ShapefileException, struct.error, ValueError, IndexError, KeyError):
        problems.append(Problem(ProblemCode.UNREADABLE_SHAPEFILE, file=name))
        return None
    return _ShapefileSet(name=name, kind=kind, records=records)


def _is_austria_lambert(prj: bytes) -> bool:
    """Whether the projection is MGI / Austria Lambert (EPSG:31287), whichever way the
    exporting software spells it."""
    text = prj.decode("latin-1")
    match = re.search(r'PROJCS\s*\[\s*"([^"]*)"', text)
    if match is None:
        return False
    return re.sub(r"[^a-z]", "", match.group(1).lower()) == "mgiaustrialambert"


def _encoding(cpg: bytes | None) -> str:
    if cpg is None:
        return _DEFAULT_ENCODING
    declared = cpg.decode("ascii", errors="ignore").strip()
    try:
        return codecs.lookup(declared).name
    except LookupError:
        return _DEFAULT_ENCODING


def _multipolygon(shape: shapefile.Shape) -> dict[str, Any] | None:
    if shape.shapeType != shapefile.POLYGON or not shape.points:
        return None
    geo = shape.__geo_interface__
    polygons = [geo["coordinates"]] if geo["type"] == "Polygon" else geo["coordinates"]
    return {
        "type": "MultiPolygon",
        "coordinates": [
            [[[float(x), float(y)] for x, y, *_ in ring] for ring in polygon]
            for polygon in polygons
        ],
    }


# --- Records -----------------------------------------------------------------------------


def _fields(source: _ShapefileSet, problems: list[Problem]) -> list[DeclaredField]:
    fields: dict[int, DeclaredField] = {}
    for index, (record, geometry) in enumerate(source.records, start=1):
        try:
            field = DeclaredField(
                number=_integer(record["FSNR"]),
                name=_text(record["FSNAME"]) or None,
                land_use_code=_required_text(record["FNAR_CODE"]),
                land_use_name=_required_text(record["FNAR"]),
                declared_area_ha=_hectares(record["FLAECHE"]),
                geometry=_required_geometry(geometry),
            )
        except ValueError as error:
            problems.append(_invalid_record(source, index, error))
            continue
        if field.number in fields:
            problems.append(Problem(ProblemCode.DUPLICATE_AREA, field_number=field.number))
        fields[field.number] = field
    return list(fields.values())


def _plots(source: _ShapefileSet, problems: list[Problem]) -> list[DeclaredPlot]:
    plots: dict[tuple[int, int], DeclaredPlot] = {}
    for index, (record, geometry) in enumerate(source.records, start=1):
        try:
            plot = DeclaredPlot(
                field_number=_integer(record["FSNR"]),
                number=_integer(record["SLNR"]),
                land_use_code=_required_text(record["SNAR_CODE"]),
                land_use_name=_required_text(record["SNAR"]),
                declared_area_ha=_hectares(record["FLAECHE_BR"]),
                geometry=_required_geometry(geometry),
            )
        except ValueError as error:
            problems.append(_invalid_record(source, index, error))
            continue
        key = (plot.field_number, plot.number)
        if key in plots:
            problems.append(
                Problem(ProblemCode.DUPLICATE_AREA, field_number=key[0], plot_number=key[1])
            )
        plots[key] = plot
    return list(plots.values())


def _invalid_record(source: _ShapefileSet, index: int, error: ValueError) -> Problem:
    return Problem(ProblemCode.INVALID_RECORD, file=source.name, detail=f"#{index}: {error}")


def _harvest_year(sets: list[_ShapefileSet], problems: list[Problem]) -> int | None:
    years: set[int] = set()
    for source in sets:
        for record, _ in source.records:
            match = _APPLICATION_TYPE.search(_text(record["FART"]))
            if match is not None:
                years.add(int(match.group(1)))
    if not years:
        problems.append(Problem(ProblemCode.MISSING_HARVEST_YEAR))
        return None
    if len(years) > 1:
        problems.append(
            Problem(ProblemCode.MIXED_HARVEST_YEARS, detail=", ".join(map(str, sorted(years))))
        )
        return None
    return years.pop()


def _check_references(
    fields: list[DeclaredField], plots: list[DeclaredPlot], problems: list[Problem]
) -> None:
    numbers = {field.number for field in fields}
    problems.extend(
        Problem(
            ProblemCode.PLOT_WITHOUT_FIELD, field_number=plot.field_number, plot_number=plot.number
        )
        for plot in plots
        if plot.field_number not in numbers
    )


def _required_geometry(geometry: dict[str, Any] | None) -> dict[str, Any]:
    if geometry is None:
        raise ValueError("no polygon")
    return geometry


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _required_text(value: Any) -> str:
    text = _text(value)
    if not text:
        raise ValueError("empty value")
    return text


def _integer(value: Any) -> int:
    """Numbers come as integers, floats or text, depending on the attribute's type."""
    try:
        number = Decimal(_text(value))
    except ArithmeticError as error:
        raise ValueError(f"not a number: {value!r}") from error
    if not number.is_finite() or number != number.to_integral_value() or number < 0:
        raise ValueError(f"not a whole number: {value!r}")
    return int(number)


def _hectares(value: Any) -> Decimal:
    if not isinstance(value, int | float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"not an area: {value!r}")
    return round(Decimal(str(value)), 4)
