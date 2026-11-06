"""Reader for farmdok's crop production log (_Pflanzenbaujournal_), a legacy `.xls` report.

The header names the farm number and the Harvest Year ("Erntejahr"); work done before
the year's harvest, e.g. cover crops sown the summer before, is listed under it. Each row
is one entry: a date, one or more Field numbers ("18, 20, 21"), the crop, the activity,
and optionally a product with its amount and unit (the unit sits in the column right of
"Menge", without a header of its own).

Pure: file content in, a `CropLog` out, or `FarmdokError` with every problem found.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import xlrd

from cropstar_api.farmdok.report import (
    FarmdokError,
    Problem,
    ProblemCode,
    below,
    open_sheet,
    same,
    text,
    whole,
)

_COLUMNS = {
    "date": "Datum",
    "fields": "Feldstück-Nr.",
    "crop": "Kultur",
    "activity": "Tätigkeit",
    "product": "Produkt",
    "amount": "Menge",
}
_DATE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
MAX_ROWS = 5000


@dataclass(frozen=True)
class CropLogEntry:
    # Spreadsheet row, counted from 1 as a spreadsheet program shows it.
    row: int
    performed_on: date
    field_numbers: tuple[int, ...]
    # As farmdok names it.
    crop: str
    activity: str
    product: str | None
    amount: Decimal | None
    # As farmdok writes it, e.g. "kg/ha", "m³/ha", "Kö/m²".
    unit: str | None


@dataclass(frozen=True)
class CropLog:
    harvest_year: int
    farm_number: str | None
    entries: tuple[CropLogEntry, ...]


def read_crop_log(content: bytes) -> CropLog:
    cells = open_sheet(content)
    is_log = any(same(v, "Pflanzenbaujournal") for row in cells[:5] for v in row)
    year = whole(below(cells, "Erntejahr"))
    header = next(
        (r for r, row in enumerate(cells[:30]) if any(same(v, _COLUMNS["date"]) for v in row)),
        None,
    )
    if not is_log or year is None or header is None:
        raise FarmdokError([Problem(ProblemCode.NOT_A_CROP_LOG)])
    columns = {
        key: next((c for c, v in enumerate(cells[header]) if same(v, label)), None)
        for key, label in _COLUMNS.items()
    }
    missing = [_COLUMNS[k] for k, c in columns.items() if c is None]
    if missing:
        raise FarmdokError([Problem(ProblemCode.MISSING_COLUMN, detail=m) for m in missing])
    amount_column = columns["amount"]
    assert amount_column is not None

    problems: list[Problem] = []
    entries: list[CropLogEntry] = []
    for index, row in enumerate(cells[header + 1 : header + 1 + MAX_ROWS], start=header + 2):

        def cell(key: str, row: list[Any] = row) -> Any:
            column = columns[key]
            return row[column] if column is not None and column < len(row) else ""

        if not any(text(v) for v in row):
            continue
        try:
            performed_on = _date(cell("date"))
            field_numbers = _field_numbers(cell("fields"))
            activity = text(cell("activity"))
            if not activity:
                raise ValueError("no activity")
            amount = _amount(cell("amount"))
            unit_cell = row[amount_column + 1] if amount_column + 1 < len(row) else ""
            unit = text(unit_cell) or None
            if amount is not None and unit is None:
                raise ValueError("an amount without unit")
        except ValueError as error:
            problems.append(Problem(ProblemCode.INVALID_ROW, row=index, detail=str(error)))
            continue
        entries.append(
            CropLogEntry(
                row=index,
                performed_on=performed_on,
                field_numbers=field_numbers,
                crop=text(cell("crop")),
                activity=activity,
                product=text(cell("product")) or None,
                amount=amount,
                unit=unit if amount is not None else None,
            )
        )
    if not entries and not problems:
        problems.append(Problem(ProblemCode.EMPTY))
    if problems:
        raise FarmdokError(problems)
    return CropLog(year, below(cells, "Betriebsnummer"), tuple(entries))


def _date(value: Any) -> date:
    if isinstance(value, float):
        # A real spreadsheet date rather than text.
        converted: datetime = xlrd.xldate_as_datetime(value, 0)
        return converted.date()
    match = _DATE.match(text(value))
    if not match:
        raise ValueError(f"not a date: {value!r}")
    day, month, year = (int(g) for g in match.groups())
    try:
        return datetime(year, month, day).date()
    except ValueError as error:
        raise ValueError(f"not a date: {value!r}") from error


def _field_numbers(value: Any) -> tuple[int, ...]:
    parts = [p for p in re.split(r"[,;]", text(value)) if p.strip()]
    numbers = [whole(p) for p in parts]
    if not numbers or any(n is None for n in numbers):
        raise ValueError(f"not Field numbers: {value!r}")
    return tuple(dict.fromkeys(n for n in numbers if n is not None))


def _amount(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value).replace(",", ".").strip())
    except InvalidOperation as error:
        raise ValueError(f"not an amount: {value!r}") from error
    if not number.is_finite() or number < 0:
        raise ValueError(f"not an amount: {value!r}")
    # farmdok computes per-hectare amounts with float noise; keep a sensible precision.
    return round(number, 4)
