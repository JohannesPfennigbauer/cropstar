"""Uploading a Harvest Year's areas from the Farm's eAMA export: preview, then confirm."""

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status
from fastapi.routing import APIRoute
from pydantic import BaseModel

from cropstar_api import area_upload
from cropstar_api.area_upload import Blocker
from cropstar_api.db import Db
from cropstar_api.eama import AreaDeclaration, EamaExportError, ProblemCode, read_export
from cropstar_api.farms import FarmMembership
from cropstar_api.geometry import ama_geojson_to_wgs84
from cropstar_api.land_use import LandUseCategory, land_use_category
from cropstar_api.models import Membership
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


class UploadedFieldProperties(BaseModel):
    # Only for telling features apart on the map; nothing is stored yet.
    id: str
    number: int
    name: str | None
    land_use_code: str
    land_use_name: str
    declared_area_ha: float


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


class UploadedPlotFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: MultiPolygon
    properties: UploadedPlotProperties


class UploadedPlotCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[UploadedPlotFeature]


class AreaUploadPreview(BaseModel):
    harvest_year: int
    field_area_ha: float
    plot_area_ha: float
    # Why the upload cannot be confirmed as it stands; empty when it can.
    blockers: list[Blocker]
    fields: UploadedFieldCollection
    plots: UploadedPlotCollection


class AreaUploadResult(BaseModel):
    harvest_year: int
    field_count: int
    plot_count: int


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
    membership: FarmMembership, db: Db, files: ExportFiles
) -> AreaUploadPreview:
    """What the export contains and whether it can be applied. Writes nothing."""
    _require_permission(membership)
    declaration = _read(files)
    shapes = iter(
        ama_geojson_to_wgs84(
            db,
            [f.geometry for f in declaration.fields] + [p.geometry for p in declaration.plots],
        )
    )
    fields = [
        UploadedFieldFeature(
            id=(key := f"field-{field.number}"),
            geometry=MultiPolygon.model_validate_json(next(shapes)),
            properties=UploadedFieldProperties(
                id=key,
                number=field.number,
                name=field.name,
                land_use_code=field.land_use_code,
                land_use_name=field.land_use_name,
                declared_area_ha=float(field.declared_area_ha),
            ),
        )
        for field in declaration.fields
    ]
    plots = [
        UploadedPlotFeature(
            id=(key := f"plot-{plot.field_number}-{plot.number}"),
            geometry=MultiPolygon.model_validate_json(next(shapes)),
            properties=UploadedPlotProperties(
                id=key,
                field_number=plot.field_number,
                number=plot.number,
                land_use_code=plot.land_use_code,
                land_use_name=plot.land_use_name,
                land_use_category=land_use_category(plot.land_use_code),
                declared_area_ha=float(plot.declared_area_ha),
            ),
        )
        for plot in declaration.plots
    ]
    return AreaUploadPreview(
        harvest_year=declaration.harvest_year,
        field_area_ha=float(sum(f.declared_area_ha for f in declaration.fields)),
        plot_area_ha=float(sum(p.declared_area_ha for p in declaration.plots)),
        blockers=area_upload.blockers(db, membership.farm_id, declaration.harvest_year),
        fields=UploadedFieldCollection(features=fields),
        plots=UploadedPlotCollection(features=plots),
    )


@router.post(
    "",
    operation_id="applyAreaUpload",
    status_code=status.HTTP_201_CREATED,
    responses=_INVALID_EXPORT,
)
def apply_area_upload(membership: FarmMembership, db: Db, files: ExportFiles) -> AreaUploadResult:
    """Creates the Fields and Plots of the export's Harvest Year. The files are read again,
    exactly as for the preview."""
    _require_permission(membership)
    declaration = _read(files)
    found = area_upload.blockers(db, membership.farm_id, declaration.harvest_year)
    if found:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=found[0].value)
    area_upload.apply(db, membership.farm_id, declaration, datetime.now(UTC))
    return AreaUploadResult(
        harvest_year=declaration.harvest_year,
        field_count=len(declaration.fields),
        plot_count=len(declaration.plots),
    )


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
