"""Reader for farmdok's field list (_Feldstücksliste_), exported as a legacy `.xls` report.

The report has a title with the Harvest Year ("Feldstücksliste 2023"), the farm number in
the header, two header rows, a SUMME row, one row per Plot and a footnote block. Field
numbers come as floats, Plot numbers as text. The Field size is only filled in when the
farm imported from AMA into farmdok, so it may be empty.

Pure: file content in, a `FieldList` out, or `FarmdokError` with every problem found.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from cropstar_api.farmdok.report import (
    FarmdokError,
    Problem,
    ProblemCode,
    below,
    hectares,
    open_sheet,
    same,
    text,
    whole,
)

_TITLE = re.compile(r"Feldst(?:ü|ue)cksliste\s+(\d{4})", re.IGNORECASE)
# Header texts as farmdok prints them; matched ignoring case and spacing.
_COLUMNS = {
    "field_number": "FSNr.",
    "field_name": "Bezeichnung",
    "field_area": "Feldstückgröße",
    "field_land_use": "Nutzungsart",
    "plot_number": "SNr.",
    "crop": "Kultur / Nutzung",
    "plot_area": "Schlaggröße",
}
_OPTIONAL = frozenset({"field_name", "field_area", "field_land_use"})
# Large enough for any farm, small enough to stop nonsense early.
MAX_ROWS = 5000


@dataclass(frozen=True)
class FieldListRow:
    field_number: int
    field_name: str | None
    # As farmdok names it, e.g. "Ackerland".
    field_land_use: str | None
    field_area_ha: Decimal | None
    plot_number: int
    # The crop as farmdok names it, e.g. "Winterweichweizen < 14 % Rohprotein".
    crop: str
    plot_area_ha: Decimal


@dataclass(frozen=True)
class FieldList:
    harvest_year: int
    farm_number: str | None
    rows: tuple[FieldListRow, ...]


def read_field_list(content: bytes) -> FieldList:
    cells = open_sheet(content)

    year = _harvest_year(cells)
    header = next(
        (
            r
            for r, row in enumerate(cells[:30])
            if any(same(v, _COLUMNS["field_number"]) for v in row)
        ),
        None,
    )
    if year is None or header is None:
        raise FarmdokError([Problem(ProblemCode.NOT_A_FIELD_LIST)])
    columns = {
        key: next((c for c, v in enumerate(cells[header]) if same(v, text)), None)
        for key, text in _COLUMNS.items()
    }
    missing = [_COLUMNS[k] for k, c in columns.items() if c is None and k not in _OPTIONAL]
    if missing:
        raise FarmdokError([Problem(ProblemCode.MISSING_COLUMN, detail=m) for m in missing])

    problems: list[Problem] = []
    rows: list[FieldListRow] = []
    seen: set[tuple[int, int]] = set()
    for index, row in enumerate(cells[header + 1 : header + 1 + MAX_ROWS], start=header + 2):

        def cell(key: str, row: list[Any] = row) -> Any:
            column = columns[key]
            return None if column is None else row[column]

        # Only rows with a Field number are Plots: this skips the second header row, the
        # SUMME row, blank rows and the footnotes.
        field_number = whole(cell("field_number"))
        if field_number is None:
            continue
        try:
            plot_number = whole(cell("plot_number"))
            if plot_number is None:
                raise ValueError("no Plot number")
            crop = text(cell("crop"))
            if not crop:
                raise ValueError("no crop")
            plot_area = hectares(cell("plot_area"))
            if plot_area is None:
                raise ValueError("no Plot size")
            field_area = hectares(cell("field_area"))
        except ValueError as error:
            problems.append(Problem(ProblemCode.INVALID_ROW, row=index, detail=str(error)))
            continue
        if (field_number, plot_number) in seen:
            detail = f"{field_number}.{plot_number}"
            problems.append(Problem(ProblemCode.DUPLICATE_PLOT, row=index, detail=detail))
            continue
        seen.add((field_number, plot_number))
        rows.append(
            FieldListRow(
                field_number=field_number,
                field_name=text(cell("field_name")) or None,
                field_land_use=text(cell("field_land_use")) or None,
                field_area_ha=field_area,
                plot_number=plot_number,
                crop=crop,
                plot_area_ha=plot_area,
            )
        )
    if not rows and not problems:
        problems.append(Problem(ProblemCode.EMPTY))
    if problems:
        raise FarmdokError(problems)
    return FieldList(year, below(cells, "Betriebsnummer"), tuple(rows))


def _harvest_year(cells: list[list[Any]]) -> int | None:
    for row in cells[:10]:
        for value in row:
            match = _TITLE.search(str(value))
            if match:
                return int(match.group(1))
    return None
