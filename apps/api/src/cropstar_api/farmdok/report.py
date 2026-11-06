"""What farmdok's `.xls` reports have in common: reading cells, and the problems found."""

import enum
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import xlrd


class ProblemCode(enum.StrEnum):
    UNREADABLE_FILE = "unreadable_file"
    NOT_A_FIELD_LIST = "not_a_field_list"
    MISSING_COLUMN = "missing_column"
    INVALID_ROW = "invalid_row"
    DUPLICATE_PLOT = "duplicate_plot"
    EMPTY = "empty"
    NOT_A_CROP_LOG = "not_a_crop_log"


@dataclass(frozen=True)
class Problem:
    code: ProblemCode
    # Spreadsheet row, counted from 1 as a spreadsheet program shows it.
    row: int | None = None
    detail: str | None = None


class FarmdokError(Exception):
    def __init__(self, problems: list[Problem]) -> None:
        self.problems = tuple(problems)
        super().__init__(", ".join(p.code for p in self.problems))


def open_sheet(content: bytes) -> list[list[Any]]:
    """The first sheet's cell values, row by row."""
    try:
        sheet = xlrd.open_workbook(file_contents=content).sheet_by_index(0)
    except Exception as error:
        problem = Problem(ProblemCode.UNREADABLE_FILE, detail=str(error)[:200])
        raise FarmdokError([problem]) from None
    return [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]


def below(cells: list[list[Any]], label: str) -> str | None:
    """The value under a header label, e.g. the farm number under "Betriebsnummer"."""
    for r, row in enumerate(cells[:10]):
        for c, value in enumerate(row):
            if same(value, label) and r + 1 < len(cells):
                return text(cells[r + 1][c]) or None
    return None


def same(value: Any, text: str) -> bool:
    return isinstance(value, str) and " ".join(value.split()).casefold() == text.casefold()


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return " ".join(str(value).split())


def whole(value: Any) -> int | None:
    """Field and Plot numbers: floats such as 12.0 or text such as "3"."""
    written = text(value)
    if not written:
        return None
    try:
        number = Decimal(written.replace(",", "."))
    except InvalidOperation:
        return None
    if not number.is_finite() or number != number.to_integral_value() or number < 0:
        return None
    return int(number)


def hectares(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value).replace(",", ".").strip())
    except InvalidOperation as error:
        raise ValueError(f"not an area: {value!r}") from error
    if not number.is_finite() or number < 0:
        raise ValueError(f"not an area: {value!r}")
    return round(number, 4)
