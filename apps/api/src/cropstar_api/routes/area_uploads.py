"""Uploading a Harvest Year's areas from the Farm's eAMA export: preview, then confirm."""

import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.routing import APIRoute
from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from cropstar_api import area_upload
from cropstar_api.area_reconciliation import (
    AreaChange,
    AreaStatus,
    AreaUploadBlocker,
    Entry,
    InvalidAssignmentError,
    Plan,
)
from cropstar_api.db import Db
from cropstar_api.eama import AreaDeclaration, EamaExportError, ProblemCode, read_export
from cropstar_api.farms import FarmMembership
from cropstar_api.geometry import ama_geojson_to_wgs84, to_wgs84_geojson
from cropstar_api.land_use import LandUseCategory, land_use_category
from cropstar_api.models import Field, Membership, Plot
from cropstar_api.policy import Action, Actor, decide
from cropstar_api.routes.areas import MultiPolygon

# One farm's export is well under a megabyte.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class _BoundedUploadRoute(APIRoute):
    """Refuses oversized requests before their multipart body is parsed and spooled."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def bounded(request: Request) -> Response:
            length = request.headers.get("content-length")
            if length is None or not length.isdigit():
                raise HTTPException(status.HTTP_411_LENGTH_REQUIRED, detail="length_required")
            if int(length) > MAX_UPLOAD_BYTES:
                raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail="upload_too_large")
            return await handler(request)

        return bounded


router = APIRouter(
    prefix="/farms/{farm_id}/area-uploads", tags=["areas"], route_class=_BoundedUploadRoute
)

ExportFiles = Annotated[
    list[UploadFile],
    File(description="The eAMA export: shapefile components (.shp, .shx, .dbf, .prj) or ZIPs"),
]
AssignmentsForm = Annotated[
    str | None,
    Form(
        description=(
            "JSON list of `Assignment`: which existing area each declared area is, or null "
            "for a new one. Declared areas left out take the suggestion, if there is one."
        )
    ),
]


class Assignment(BaseModel):
    # The declared area, as in the preview: `field-3` or `plot-3-1`.
    key: str
    # The existing Field or Plot it is; null for a new one without history.
    target: uuid.UUID | None


_ASSIGNMENTS = TypeAdapter(list[Assignment])


class AreaCandidate(BaseModel):
    id: uuid.UUID
    # The share of the declared area lying on the existing one, from 0 to 1.
    coverage: float


class AreaDecision(BaseModel):
    """What happens to a declared area, given the assignments so far."""

    status: AreaStatus
    # The existing area it is; null when it is new or still undecided.
    target: uuid.UUID | None
    decided: bool
    # Whether the decision is Cropstar's suggestion rather than the Admin's own choice.
    suggested: bool
    changes: list[AreaChange]
    # Overlapping existing areas, most covered first.
    candidates: list[AreaCandidate]


class UploadedFieldProperties(BaseModel):
    # The key to assign it by, and to tell features apart on the map.
    id: str
    number: int
    name: str | None
    land_use_code: str
    land_use_name: str
    declared_area_ha: float
    decision: AreaDecision


class UploadedFieldFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: MultiPolygon
    properties: UploadedFieldProperties


class UploadedFieldCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[UploadedFieldFeature]


class UploadedPlotProperties(BaseModel):
    id: str
    field_number: int
    number: int
    land_use_code: str
    land_use_name: str
    land_use_category: LandUseCategory
    declared_area_ha: float
    decision: AreaDecision


class UploadedPlotFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: MultiPolygon
    properties: UploadedPlotProperties


class UploadedPlotCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[UploadedPlotFeature]


class TaskRef(BaseModel):
    id: uuid.UUID
    title: str


class CurrentFieldProperties(BaseModel):
    id: uuid.UUID
    number: int
    name: str | None
    land_use_code: str
    land_use_name: str
    declared_area_ha: float
    # Whether the upload, as assigned so far, removes it.
    removed: bool
    # Tasks referring to it: removing it would lose their record.
    tasks: list[TaskRef]


class CurrentFieldFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: uuid.UUID
    geometry: MultiPolygon
    properties: CurrentFieldProperties


class CurrentFieldCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[CurrentFieldFeature]


class CurrentPlotProperties(BaseModel):
    id: uuid.UUID
    field_id: uuid.UUID
    field_number: int
    number: int
    land_use_code: str
    land_use_name: str
    land_use_category: LandUseCategory
    declared_area_ha: float
    removed: bool
    tasks: list[TaskRef]


class CurrentPlotFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: uuid.UUID
    geometry: MultiPolygon
    properties: CurrentPlotProperties


class CurrentPlotCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[CurrentPlotFeature]


class AreaUploadPreview(BaseModel):
    harvest_year: int
    field_area_ha: float
    plot_area_ha: float
    # Why the upload cannot be confirmed as it stands; empty when it can.
    blockers: list[AreaUploadBlocker]
    fields: UploadedFieldCollection
    plots: UploadedPlotCollection
    # The Harvest Year's areas as they are now.
    current_fields: CurrentFieldCollection
    current_plots: CurrentPlotCollection


class AreaUploadResult(BaseModel):
    harvest_year: int
    field_count: int
    plot_count: int
    # Fields and Plots together.
    created_count: int
    changed_count: int
    removed_count: int


class ExportProblem(BaseModel):
    code: ProblemCode
    file: str | None
    field_number: int | None
    plot_number: int | None
    detail: str | None


class InvalidExport(BaseModel):
    code: Literal["invalid_eama_export"] = "invalid_eama_export"
    problems: list[ExportProblem]


class InvalidExportResponse(BaseModel):
    detail: InvalidExport


_INVALID_EXPORT: dict[int | str, dict[str, Any]] = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": InvalidExportResponse}
}


@router.post("/preview", operation_id="previewAreaUpload", responses=_INVALID_EXPORT)
def preview_area_upload(
    membership: FarmMembership,
    db: Db,
    files: ExportFiles,
    assignments: AssignmentsForm = None,
) -> AreaUploadPreview:
    """What the export would do to its Harvest Year, given the assignments so far, and
    whether it can be applied. Writes nothing."""
    _require_permission(membership)
    declaration = _read(files)
    current = area_upload.current_areas(db, membership.farm_id, declaration.harvest_year)
    plan = _reconcile(current, declaration, assignments)
    shapes = iter(
        ama_geojson_to_wgs84(
            db,
            [f.geometry for f in declaration.fields] + [p.geometry for p in declaration.plots],
        )
    )
    fields = [
        UploadedFieldFeature(
            id=entry.key,
            geometry=MultiPolygon.model_validate_json(next(shapes)),
            properties=UploadedFieldProperties(
                id=entry.key,
                number=field.number,
                name=field.name,
                land_use_code=field.land_use_code,
                land_use_name=field.land_use_name,
                declared_area_ha=float(field.declared_area_ha),
                decision=_decision(entry),
            ),
        )
        for field, entry in zip(declaration.fields, plan.fields, strict=True)
    ]
    plots = [
        UploadedPlotFeature(
            id=entry.key,
            geometry=MultiPolygon.model_validate_json(next(shapes)),
            properties=UploadedPlotProperties(
                id=entry.key,
                field_number=plot.field_number,
                number=plot.number,
                land_use_code=plot.land_use_code,
                land_use_name=plot.land_use_name,
                land_use_category=land_use_category(plot.land_use_code),
                declared_area_ha=float(plot.declared_area_ha),
                decision=_decision(entry),
            ),
        )
        for plot, entry in zip(declaration.plots, plan.plots, strict=True)
    ]
    geometries = _current_geometries(db, current)
    tasks = current.tasks
    removed = {*plan.removed_fields, *plan.removed_plots}
    field_numbers = {field.id: field.number for field in current.fields}
    return AreaUploadPreview(
        harvest_year=declaration.harvest_year,
        field_area_ha=float(sum(f.declared_area_ha for f in declaration.fields)),
        plot_area_ha=float(sum(p.declared_area_ha for p in declaration.plots)),
        blockers=list(plan.blockers),
        fields=UploadedFieldCollection(features=fields),
        plots=UploadedPlotCollection(features=plots),
        current_fields=CurrentFieldCollection(
            features=[
                CurrentFieldFeature(
                    id=field.id,
                    geometry=geometries[field.id],
                    properties=CurrentFieldProperties(
                        id=field.id,
                        number=field.number,
                        name=field.name,
                        land_use_code=field.land_use_code,
                        land_use_name=field.land_use_name,
                        declared_area_ha=float(field.declared_area_ha),
                        removed=field.id in removed,
                        tasks=_task_refs(tasks.get(field.id, [])),
                    ),
                )
                for field in current.fields
            ]
        ),
        current_plots=CurrentPlotCollection(
            features=[
                CurrentPlotFeature(
                    id=plot.id,
                    geometry=geometries[plot.id],
                    properties=CurrentPlotProperties(
                        id=plot.id,
                        field_id=plot.field_id,
                        field_number=field_numbers[plot.field_id],
                        number=plot.number,
                        land_use_code=plot.land_use_code,
                        land_use_name=plot.land_use_name,
                        land_use_category=land_use_category(plot.land_use_code),
                        declared_area_ha=float(plot.declared_area_ha),
                        removed=plot.id in removed,
                        tasks=_task_refs(tasks.get(plot.id, [])),
                    ),
                )
                for plot in current.plots
            ]
        ),
    )


@router.post("", operation_id="applyAreaUpload", responses=_INVALID_EXPORT)
def apply_area_upload(
    membership: FarmMembership,
    db: Db,
    files: ExportFiles,
    assignments: AssignmentsForm = None,
) -> AreaUploadResult:
    """Makes the export's Harvest Year match it: assigned areas are updated in place and keep
    their Tasks and Operations, unassigned ones are removed. The files are read again and
    reconciled exactly as for the preview."""
    _require_permission(membership)
    declaration = _read(files)
    current = area_upload.current_areas(db, membership.farm_id, declaration.harvest_year)
    plan = _reconcile(current, declaration, assignments)
    if plan.blockers:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=plan.blockers[0].value)
    area_upload.apply(db, membership.farm_id, declaration, current, plan, datetime.now(UTC))
    entries = (*plan.fields, *plan.plots)
    return AreaUploadResult(
        harvest_year=declaration.harvest_year,
        field_count=len(declaration.fields),
        plot_count=len(declaration.plots),
        created_count=sum(e.status == AreaStatus.NEW for e in entries),
        changed_count=sum(e.status == AreaStatus.CHANGED for e in entries),
        removed_count=len(plan.removed_fields) + len(plan.removed_plots),
    )


def _reconcile(
    current: area_upload.CurrentAreas, declaration: AreaDeclaration, assignments: str | None
) -> Plan:
    try:
        parsed = _ASSIGNMENTS.validate_json(assignments or "[]")
        if len({a.key for a in parsed}) != len(parsed):
            raise InvalidAssignmentError("an area is assigned twice")
        return area_upload.reconcile(current, declaration, {a.key: a.target for a in parsed})
    except (ValidationError, InvalidAssignmentError) as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_assignments"
        ) from error


def _decision(entry: Entry) -> AreaDecision:
    return AreaDecision(
        status=entry.status,
        target=entry.target,
        decided=entry.decided,
        suggested=entry.suggested,
        changes=list(entry.changes),
        candidates=[AreaCandidate(id=c.id, coverage=c.coverage) for c in entry.candidates],
    )


def _current_geometries(
    db: Session, current: area_upload.CurrentAreas
) -> dict[uuid.UUID, MultiPolygon]:
    rows = [
        *db.execute(
            select(Field.id, to_wgs84_geojson(Field.geometry)).where(
                Field.id.in_([f.id for f in current.fields])
            )
        ),
        *db.execute(
            select(Plot.id, to_wgs84_geojson(Plot.geometry)).where(
                Plot.id.in_([p.id for p in current.plots])
            )
        ),
    ]
    return {area_id: MultiPolygon.model_validate_json(geojson) for area_id, geojson in rows}


def _task_refs(refs: list[area_upload.TaskRef]) -> list[TaskRef]:
    return [TaskRef(id=ref.id, title=ref.title) for ref in refs]


def _require_permission(membership: Membership) -> None:
    decision = decide(Actor(membership.user_id, membership.role), Action.UPLOAD_AREAS)
    if not decision:
        assert decision.denial is not None
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=decision.denial.value)


def _read(files: list[UploadFile]) -> AreaDeclaration:
    try:
        return read_export((file.filename or "", file.file.read()) for file in files)
    except EamaExportError as error:
        invalid = InvalidExport(
            problems=[
                ExportProblem(
                    code=p.code,
                    file=p.file,
                    field_number=p.field_number,
                    plot_number=p.plot_number,
                    detail=p.detail,
                )
                for p in error.problems
            ]
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail=invalid.model_dump(mode="json")
        ) from error
