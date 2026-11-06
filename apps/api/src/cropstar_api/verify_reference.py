"""`cropstar-api verify-reference`: check a Farm on any Cropstar instance against reports.

Talks to the instance over its HTTP API as a member of the Farm, so the same command checks
a local rehearsal and production. The reports are read locally and never sent anywhere.
"""

import getpass
import json
import os
import re
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from cropstar_api.eama import AreaDeclaration, EamaExportError, ProblemCode, read_export
from cropstar_api.farmdok.crop_log import CropLog, read_crop_log
from cropstar_api.farmdok.field_list import FieldList, read_field_list
from cropstar_api.farmdok.report import FarmdokError
from cropstar_api.reference_check import (
    Finding,
    Severity,
    YearState,
    check_crop_log,
    check_eama,
    check_field_list,
)

_SHAPEFILE_PARTS = {".shp", ".shx", ".dbf", ".prj", ".cpg", ".zip"}
_YEAR_IN_NAME = re.compile(r"MFA(\d{4})")
_MARKS = {Severity.OK: "✓", Severity.CHECK: "?", Severity.MISMATCH: "✗"}


class Instance:
    """A signed-in session with a Cropstar instance."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookie = ""

    def sign_in(self, email: str, password: str) -> None:
        response = self._request(
            "POST", "/api/auth/sign-in", {"email": email, "password": password}
        )
        # The session cookie is Secure; urllib's cookie jar would drop it on plain http.
        cookies = [
            header.split(";", 1)[0]
            for name, header in response.getheaders()
            if name.lower() == "set-cookie"
        ]
        self.cookie = "; ".join(cookies)

    def get(self, path: str, **query: Any) -> Any:
        suffix = f"?{urllib.parse.urlencode(query, doseq=True)}" if query else ""
        with self._request("GET", path + suffix) as response:
            return json.load(response)

    def _request(self, method: str, path: str, body: Any = None) -> Any:
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Cookie": self.cookie},
        )
        return urllib.request.urlopen(request, timeout=30)


def read_reports(
    directory: Path,
) -> tuple[list[AreaDeclaration], list[FieldList], list[CropLog], list[str]]:
    """Every eAMA export, field list and crop log at the top level of `directory`."""
    files = sorted(p for p in directory.iterdir() if p.is_file())
    notes: list[str] = []
    exports: dict[str, list[Path]] = {}
    for path in files:
        if path.suffix.lower() in _SHAPEFILE_PARTS:
            year = _YEAR_IN_NAME.search(path.name)
            exports.setdefault(year.group(1) if year else "", []).append(path)
    declarations = []
    for group in exports.values():
        try:
            declarations.append(read_export((p.name, p.read_bytes()) for p in group))
        except EamaExportError as error:
            codes = {p.code for p in error.problems}
            if codes != {ProblemCode.NO_FILES}:
                notes.append(f"eAMA-Export nicht lesbar ({', '.join(sorted(codes))})")
    field_lists, logs = [], []
    for path in files:
        if path.suffix.lower() != ".xls":
            continue
        content = path.read_bytes()
        try:
            field_lists.append(read_field_list(content))
            continue
        except FarmdokError:
            pass
        try:
            logs.append(read_crop_log(content))
        except FarmdokError:
            notes.append(
                f"{path.name}: weder Feldstücksliste noch Pflanzenbaujournal, übersprungen"
            )
    return declarations, field_lists, logs, notes


def verify(
    instance: Instance,
    farm_id: str,
    declarations: Iterable[AreaDeclaration],
    field_lists: Iterable[FieldList],
    logs: Iterable[CropLog],
) -> list[Finding]:
    by_eama = {d.harvest_year: d for d in declarations}
    by_list = {f.harvest_year: f for f in field_lists}
    by_log = {log.harvest_year: log for log in logs}
    findings: list[Finding] = []
    for year in sorted({*by_eama, *by_list, *by_log}):
        state = YearState(
            plots=[
                {**f["properties"], "geometry": f["geometry"]}
                for f in instance.get(f"/api/farms/{farm_id}/plots", harvest_year=year)["features"]
            ],
            tasks=[
                t
                for t in instance.get(
                    f"/api/farms/{farm_id}/tasks", harvest_year=year, status="done"
                )
                if t["harvest_year"] == year
            ],
        )
        if year in by_eama:
            findings += check_eama(by_eama[year], state)
        elif year in by_list:
            findings += check_field_list(by_list[year], state)
        if year in by_log:
            findings += check_crop_log(by_log[year], state)
    return findings


def run(base_url: str, email: str, farm: str, directory: Path) -> int:
    declarations, field_lists, logs, notes = read_reports(directory)
    for note in notes:
        print(f"! {note}")
    password = os.environ.get("CROPSTAR_PASSWORD") or getpass.getpass(f"Passwort für {email}: ")
    instance = Instance(base_url)
    instance.sign_in(email, password)
    memberships = instance.get("/api/me")["memberships"]
    chosen = [m["farm"] for m in memberships if farm in (m["farm"]["id"], m["farm"]["name"])]
    if len(chosen) != 1:
        names = ", ".join(m["farm"]["name"] for m in memberships)
        print(f"Betrieb „{farm}“ nicht eindeutig gefunden. Deine Betriebe: {names}")
        return 2
    findings = verify(instance, chosen[0]["id"], declarations, field_lists, logs)
    year = None
    for finding in findings:
        if finding.harvest_year != year:
            year = finding.harvest_year
            print(f"\nErntejahr {year}")
        print(f"  {_MARKS[finding.severity]} {finding.message}")
    counts = {s: sum(f.severity is s for f in findings) for s in Severity}
    print(
        f"\n{counts[Severity.OK]} passt, {counts[Severity.CHECK]} zu prüfen, "
        f"{counts[Severity.MISMATCH]} weicht ab"
    )
    return 1 if counts[Severity.MISMATCH] else 0
