"""Synthetic farmdok field lists for tests, laid out like farmdok's `.xls` report.

Never use a real farm's report in tests: it is commercially sensitive. Run as a module to
write one for the end-to-end tests:

    uv run python -m tests.farmdok_export <path.xls> [year] [field_list|crop_log]
    (from apps/api)
"""

import io
import sys
from dataclasses import dataclass
from pathlib import Path

import xlwt


@dataclass(frozen=True)
class Row:
    field_number: int
    field_name: str
    plot_number: int
    crop: str
    plot_area_ha: float
    field_land_use: str = "Ackerland"


# The demo Farm's Fields and Plots (see `eama_export`), as farmdok would list them.
DEMO_ROWS = (
    Row(1, "Kellerberg", 1, "Winterroggen", 4.8094),
    Row(1, "Kellerberg", 2, "Grünbrache", 0.441),
    Row(2, "Am Graben", 1, "Sonnenblumen", 2.7669),
    Row(2, "Am Graben", 2, "Sommerbraugerste", 0.6865),
)


def field_list(rows: tuple[Row, ...] = DEMO_ROWS, year: int = 2025) -> bytes:
    book = xlwt.Workbook(encoding="utf-8")
    sheet = book.add_sheet("Sheet1_1")
    sheet.write(0, 0, f"Feldstücksliste {year}")
    sheet.write(1, 0, "Name/Betrieb Adresse")
    sheet.write(1, 6, "Betriebsnummer")
    sheet.write(2, 0, "Hof Muster")
    sheet.write(2, 6, "9999999")
    sheet.write(3, 0, "1234 Musterdorf")
    headers = [
        "FSNr.",
        "Bezeichnung",
        "Feldstückgröße",
        "",
        "Nutzungsart",
        "SNr.",
        "Kultur / Nutzung",
        "Schlaggröße",
    ]
    for column, text in enumerate(headers):
        sheet.write(5, column, text)
    for column, text in ((0, "MFA"), (2, "in ha, lt. AMA Import"), (5, "Schlag"), (7, "in ha")):
        sheet.write(6, column, text)
    sheet.write(7, 0, "SUMME")
    sheet.write(7, 7, sum(r.plot_area_ha for r in rows))
    # farmdok sorts Field numbers as text: 1, 10, 11, 2, …
    ordered = sorted(rows, key=lambda r: (str(r.field_number), r.plot_number))
    for index, row in enumerate(ordered, start=8):
        sheet.write(index, 0, float(row.field_number))
        sheet.write(index, 1, row.field_name)
        sheet.write(index, 4, row.field_land_use)
        sheet.write(index, 5, str(row.plot_number))
        sheet.write(index, 6, row.crop)
        sheet.write(index, 7, row.plot_area_ha)
    footer = 8 + len(rows) + 1
    sheet.write(footer, 0, "Hinweis:")
    sheet.write(footer + 1, 0, "Die Feldstückgröße wird im Falle eines AMA-Imports gesetzt.")
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


@dataclass(frozen=True)
class Entry:
    day: str
    fields: str
    crop: str
    activity: str
    product: str = ""
    amount: float | None = None
    unit: str = ""


# Work on the demo Farm's Plots (see `DEMO_ROWS`), as farmdok would log it.
DEMO_ENTRIES = (
    Entry("28.08.2024", "1", "Winterroggen", "Wirtschaftsdünger Mist", "Rindermist", 25.0, "m³/ha"),
    Entry("02.09.2024", "1", "Winterroggen", "Scheibenegge"),
    Entry("02.10.2024", "1", "Winterroggen", "Aussaat Hauptkultur", "Winterroggen", 140.0, "kg/ha"),
    Entry("25.03.2025", "1", "Winterroggen", "Striegeln"),
    Entry("20.07.2025", "1", "Winterroggen", "Mähdrusch", "Winterroggen", 5432.1, "kg/ha"),
)


def crop_log(entries: tuple[Entry, ...] = DEMO_ENTRIES, year: int = 2025) -> bytes:
    book = xlwt.Workbook(encoding="utf-8")
    sheet = book.add_sheet("Sheet1_1")
    sheet.write(0, 0, "Pflanzenbaujournal")
    sheet.write(1, 0, "Name/Betrieb Adresse")
    sheet.write(1, 4, "Betriebsnummer")
    sheet.write(1, 5, "Erntejahr")
    sheet.write(2, 0, "Hof Muster")
    sheet.write(2, 4, "9999999")
    sheet.write(2, 5, str(year))
    for column, text in enumerate(
        ["Datum", "Feldstück-Nr.", "Kultur", "Tätigkeit", "Produkt", "Menge"]
    ):
        sheet.write(5, column, text)
    for index, entry in enumerate(entries, start=6):
        for column, value in enumerate(
            [entry.day, entry.fields, entry.crop, entry.activity, entry.product]
        ):
            if value:
                sheet.write(index, column, value)
        if entry.amount is not None:
            sheet.write(index, 5, entry.amount)
            sheet.write(index, 6, entry.unit)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


if __name__ == "__main__":
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    year = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
    report = sys.argv[3] if len(sys.argv) > 3 else "field_list"
    target.write_bytes(crop_log(year=year) if report == "crop_log" else field_list(year=year))
