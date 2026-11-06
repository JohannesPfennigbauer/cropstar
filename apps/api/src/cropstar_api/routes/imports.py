"""Imports from farmdok: field lists and crop production logs; preview, confirm, list, undo."""

import json
import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal, NoReturn

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cropstar_api.db import Db
from cropstar_api.farmdok import crop_log_import, field_list_import
from cropstar_api.farmdok.crop_log import CropLog, read_crop_log
from cropstar_api.farmdok.crop_log_plan import (
    INPUT_KINDS,
    CropLogPlan,
    InvalidResolutionError,
    ProductChoice,
    Resolutions,
    can_create_seed,
)
from cropstar_api.farmdok.crop_log_plan import Problem as CropLogProblem
from cropstar_api.farmdok.field_list import FieldList, read_field_list
from cropstar_api.farmdok.field_list_import import Blocker, Borrowed
from cropstar_api.farmdok.field_list_plan import (
    FieldListPlan,
    GeometryMatch,
    InvalidCropAssignmentError,
    nearest_year,
)
from cropstar_api.farmdok.report import FarmdokError, ProblemCode
from cropstar_api.farms import FarmMembership
from cropstar_api.land_use import LandUseCategory, land_use_category
from cropstar_api.models import (
    FarmdokTermKind,
    FarmInput,
    FarmInputKind,
    Field,
    ImportBatch,
    ImportKind,
    Membership,
    OperationType,
    Plot,
    Task,
    User,
)
from cropstar_api.operation_details import OperationDetails
from cropstar_api.policy import Action, Actor, decide
from cropstar_api.routes.area_uploads import BoundedUploadRoute
from cropstar_api.routes.areas import MultiPolygon

router = APIRouter(prefix="/farms/{farm_id}", tags=["imports"], route_class=BoundedUploadRoute)

ReportFile = Annotated[UploadFile, File(description="farmdok's field list (Feldstücksliste), .xls")]
ReferenceYear = Annotated[
    int | None,
    Form(description="Harvest Year to borrow geometry from; default: the nearest with eAMA"),
]
CropAssignments = Annotated[
    str | None,
    Form(description="JSON object: farmdok crop name → AMA Land Use code, for unknown crops"),
]
_ASSIGNMENTS = TypeAdapter(dict[str, str])


# ── Schemas ─────────────────────────────────────────────────────────────────


class ImportedFieldProperties(BaseModel):
    id: str
    number: int
    name: str | None
    land_use_name: str
    declared_area_ha: float
    geometry_match: GeometryMatch


class ImportedFieldFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: MultiPolygon | None
    properties: ImportedFieldProperties


class ImportedFieldCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ImportedFieldFeature]


class ImportedPlotProperties(BaseModel):
    id: str
    field_number: int
    number: int
    # As farmdok names it.
    crop: str
    # Null while the crop is unknown.
    land_use_code: str | None
    land_use_name: str | None
    land_use_category: LandUseCategory
    declared_area_ha: float
    geometry_match: GeometryMatch


class ImportedPlotFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: MultiPolygon | None
    properties: ImportedPlotProperties


class ImportedPlotCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ImportedPlotFeature]


class UnknownCropOut(BaseModel):
    name: str
    plot_count: int


class FieldListPreview(BaseModel):
    harvest_year: int
    # The year geometry is borrowed from; null when there is none to borrow from.
    reference_year: int | None
    # Years with an eAMA export to choose from.
    reference_years: list[int]
    blockers: list[Blocker]
    unknown_crops: list[UnknownCropOut]
    # How many Plots get the matching Plot's geometry, their Field's, or none.
    geometry_counts: dict[GeometryMatch, int]
    plot_area_ha: float
    fields: ImportedFieldCollection
    plots: ImportedPlotCollection


class ImportBatchOut(BaseModel):
    id: uuid.UUID
    kind: ImportKind
    harvest_year: int
    source_name: str
    created_by: str | None
    created_at: datetime
    field_count: int
    plot_count: int
    task_count: int


class LogPlotRef(BaseModel):
    id: uuid.UUID
    field_number: int
    number: int
    land_use_name: str


class LogInputRef(BaseModel):
    id: uuid.UUID
    name: str
    kind: FarmInputKind
    archived: bool


class LogEntryOut(BaseModel):
    row: int
    performed_on: date
    field_numbers: list[int]
    crop: str
    activity: str
    product: str | None


class PlannedTaskOut(BaseModel):
    row: int
    performed_on: date
    title: str
    operation_type: str
    plots: list[LogPlotRef]
    details: OperationDetails
    # The Farm Input the details refer to, existing or to be created.
    farm_input_name: str | None


class UnresolvedOut(BaseModel):
    problem: CropLogProblem
    # The activity, the product, or the entry's row.
    key: str
    entries: list[LogEntryOut]
    # Product problems: which kind of Farm Input fits, and whether one can be created.
    input_kind: FarmInputKind | None
    can_create: bool


class CropLogPreview(BaseModel):
    harvest_year: int
    blockers: list[crop_log_import.Blocker]
    entry_count: int
    operation_count: int
    skipped_rows: list[int]
    tasks: list[PlannedTaskOut]
    unresolved: list[UnresolvedOut]
    # Farm Inputs the import will create.
    new_inputs: list[str]
    # What resolutions can choose from.
    plots: list[LogPlotRef]
    farm_inputs: list[LogInputRef]
    operation_types: list[str]


class ProductResolution(BaseModel):
    """One of: an existing Farm Input, `create` one named like the product, or `none`."""

    farm_input_id: uuid.UUID | None = None
    create: bool = False
    none: bool = False


class LogResolutions(BaseModel):
    # Activity → Operation Type, or null to skip its entries.
    activities: dict[str, str | None] = {}
    products: dict[str, ProductResolution] = {}
    # Spreadsheet row → Plot ids, or null to skip the entry.
    entries: dict[int, list[uuid.UUID] | None] = {}


class ImportProblem(BaseModel):
    code: ProblemCode
    row: int | None
    detail: str | None


class InvalidReport(BaseModel):
    code: Literal["invalid_farmdok_report"] = "invalid_farmdok_report"
    problems: list[ImportProblem]


class InvalidReportResponse(BaseModel):
    detail: InvalidReport


_INVALID_REPORT: dict[int | str, dict[str, Any]] = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": InvalidReportResponse}
}


# ── Routes ──────────────────────────────────────────────────────────────────


@router.post(
    "/imports/farmdok-field-list/preview",
    operation_id="previewFarmdokFieldList",
    responses=_INVALID_REPORT,
)
def preview_field_list(
    membership: FarmMembership,
    db: Db,
    file: ReportFile,
    reference_year: ReferenceYear = None,
    crop_assignments: CropAssignments = None,
) -> FieldListPreview:
    """What the field list would create, with geometry borrowed from another year. Writes
    nothing."""
    _require(membership, Action.IMPORT_DATA)
    field_list = _read(file)
    years = field_list_import.reference_years(db, membership.farm_id)
    planned = _plan(db, membership, field_list, years, reference_year, crop_assignments)
    return FieldListPreview(
        harvest_year=planned.harvest_year,
        reference_year=planned.reference_year,
        reference_years=sorted(years - {planned.harvest_year}),
        blockers=field_list_import.blockers(db, membership.farm_id, planned),
        unknown_crops=[
            UnknownCropOut(name=c.name, plot_count=c.plot_count) for c in planned.unknown_crops
        ],
        geometry_counts=field_list_import.geometry_counts(planned),
        plot_area_ha=float(sum(p.declared_area_ha for p in planned.plots)),
        fields=ImportedFieldCollection(
            features=[
                ImportedFieldFeature(
                    id=(key := f"field-{f.number}"),
                    geometry=_wgs84(f.geometry),
                    properties=ImportedFieldProperties(
                        id=key,
                        number=f.number,
                        name=f.name,
                        land_use_name=f.land_use_name,
                        declared_area_ha=float(f.declared_area_ha),
                        geometry_match=f.match,
                    ),
                )
                for f in planned.fields
            ]
        ),
        plots=ImportedPlotCollection(
            features=[
                ImportedPlotFeature(
                    id=(key := f"plot-{p.field_number}-{p.number}"),
                    geometry=_wgs84(p.geometry),
                    properties=ImportedPlotProperties(
                        id=key,
                        field_number=p.field_number,
                        number=p.number,
                        crop=p.crop,
                        land_use_code=p.land_use[0] if p.land_use else None,
                        land_use_name=p.land_use[1] if p.land_use else None,
                        land_use_category=land_use_category(p.land_use[0] if p.land_use else ""),
                        declared_area_ha=float(p.declared_area_ha),
                        geometry_match=p.match,
                    ),
                )
                for p in planned.plots
            ]
        ),
    )


@router.post(
    "/imports/farmdok-field-list",
    operation_id="importFarmdokFieldList",
    status_code=status.HTTP_201_CREATED,
    responses=_INVALID_REPORT,
)
def import_field_list(
    membership: FarmMembership,
    db: Db,
    file: ReportFile,
    reference_year: ReferenceYear = None,
    crop_assignments: CropAssignments = None,
) -> ImportBatchOut:
    """Creates the Harvest Year's Fields and Plots as one import batch. The report is read
    and planned again, exactly as for the preview."""
    _require(membership, Action.IMPORT_DATA)
    field_list = _read(file)
    years = field_list_import.reference_years(db, membership.farm_id)
    planned = _plan(db, membership, field_list, years, reference_year, crop_assignments)
    found = field_list_import.blockers(db, membership.farm_id, planned)
    if found:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=found[0].value)
    now = datetime.now(UTC)
    batch = field_list_import.apply(
        db,
        membership.farm_id,
        membership.user_id,
        file.filename or "Feldstücksliste.xls",
        planned,
        now,
    )
    for name, code in _ASSIGNMENTS.validate_json(crop_assignments or "{}").items():
        field_list_import.remember(
            db, membership.farm_id, FarmdokTermKind.CROP, name, now, land_use_code=code
        )
    return _batches(db, membership.farm_id, batch.id)[0]


LogResolutionsForm = Annotated[
    str | None,
    Form(description="JSON `LogResolutions`: answers to what the preview could not decide"),
]
_RESOLUTIONS = TypeAdapter(LogResolutions)


@router.post(
    "/imports/farmdok-crop-log/preview",
    operation_id="previewFarmdokCropLog",
    responses=_INVALID_REPORT,
)
def preview_crop_log(
    membership: FarmMembership,
    db: Db,
    file: ReportFile,
    resolutions: LogResolutionsForm = None,
) -> CropLogPreview:
    """The Done Tasks the crop production log would create, and what is left to decide.
    Writes nothing."""
    _require(membership, Action.IMPORT_DATA)
    log = _read_log(file)
    parsed = _to_resolutions(_resolutions(resolutions))
    planned = _plan_log(db, membership, log, parsed)
    plots = {
        plot.id: LogPlotRef(
            id=plot.id,
            field_number=field_number,
            number=plot.number,
            land_use_name=plot.land_use_name,
        )
        for plot, field_number in db.execute(
            select(Plot, Field.number)
            .join(Field, Plot.field_id == Field.id)
            .where(Field.farm_id == membership.farm_id, Field.harvest_year == log.harvest_year)
            .order_by(Field.number, Plot.number)
        )
    }
    inputs = list(
        db.scalars(
            select(FarmInput)
            .where(FarmInput.farm_id == membership.farm_id)
            .order_by(FarmInput.name)
        )
    )
    names = {i.id: i.name for i in inputs}
    entries = {e.row: e for e in log.entries}

    def entry_out(row: int) -> LogEntryOut:
        e = entries[row]
        return LogEntryOut(
            row=e.row,
            performed_on=e.performed_on,
            field_numbers=list(e.field_numbers),
            crop=e.crop,
            activity=e.activity,
            product=e.product,
        )

    def input_kind(problem: CropLogProblem, context: tuple[str, ...]) -> FarmInputKind | None:
        if problem in (CropLogProblem.UNKNOWN_PRODUCT, CropLogProblem.UNIT_MISMATCH) and context:
            return INPUT_KINDS.get(context[0])
        return None

    unresolved = []
    for u in planned.unresolved:
        kind = input_kind(u.problem, u.context)
        unresolved.append(
            UnresolvedOut(
                problem=u.problem,
                key=u.key,
                entries=[entry_out(row) for row in u.rows],
                input_kind=kind,
                can_create=kind is FarmInputKind.FERTILISER
                or (kind is FarmInputKind.SEED and can_create_seed(u.key)),
            )
        )
    return CropLogPreview(
        harvest_year=planned.harvest_year,
        blockers=crop_log_import.blockers(db, membership.farm_id, planned),
        entry_count=planned.entry_count,
        operation_count=sum(len(t.plot_ids) for t in planned.tasks),
        skipped_rows=list(planned.skipped_rows),
        tasks=[
            PlannedTaskOut(
                row=t.row,
                performed_on=t.performed_on,
                title=t.title,
                operation_type=t.operation_type,
                plots=[plots[i] for i in t.plot_ids if i in plots],
                details=t.details,
                farm_input_name=t.new_input
                or names.get(getattr(t.details, "farm_input_id", None) or uuid.UUID(int=0)),
            )
            for t in planned.tasks
        ],
        unresolved=unresolved,
        new_inputs=[n.name for n in planned.new_inputs],
        plots=list(plots.values()),
        farm_inputs=[
            LogInputRef(id=i.id, name=i.name, kind=i.kind, archived=i.archived_at is not None)
            for i in inputs
        ],
        operation_types=list(
            db.scalars(select(OperationType.code).order_by(OperationType.position))
        ),
    )


@router.post(
    "/imports/farmdok-crop-log",
    operation_id="importFarmdokCropLog",
    status_code=status.HTTP_201_CREATED,
    responses=_INVALID_REPORT,
)
def import_crop_log(
    membership: FarmMembership,
    db: Db,
    file: ReportFile,
    resolutions: LogResolutionsForm = None,
) -> ImportBatchOut:
    """Creates the Done Tasks as one import batch and remembers the answers given for
    activities and products. The report is read and planned again, as for the preview."""
    _require(membership, Action.IMPORT_DATA)
    log = _read_log(file)
    parsed = _to_resolutions(_resolutions(resolutions))
    planned = _plan_log(db, membership, log, parsed)
    found = crop_log_import.blockers(db, membership.farm_id, planned)
    if found:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=found[0].value)
    batch = crop_log_import.apply(
        db,
        membership.farm_id,
        membership.user_id,
        file.filename or "Pflanzenbaujournal.xls",
        planned,
        parsed,
        datetime.now(UTC),
    )
    return _batches(db, membership.farm_id, batch.id)[0]


@router.get("/import-batches", operation_id="listImportBatches")
def list_import_batches(membership: FarmMembership, db: Db) -> list[ImportBatchOut]:
    return _batches(db, membership.farm_id)


@router.delete(
    "/import-batches/{batch_id}",
    operation_id="undoImportBatch",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def undo_import_batch(batch_id: uuid.UUID, membership: FarmMembership, db: Db) -> None:
    """Removes everything the import created. Refused for a Locked Harvest Year and once
    Tasks refer to the imported areas."""
    _require(membership, Action.UNDO_IMPORT)
    batch = db.get(ImportBatch, batch_id)
    if batch is None or batch.farm_id != membership.farm_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="import_batch_not_found")
    service = crop_log_import if batch.kind is ImportKind.FARMDOK_CROP_LOG else field_list_import
    refusal = service.undo_refusal(db, batch)
    if refusal is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=refusal.value)
    service.undo(db, batch)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _require(membership: Membership, action: Action) -> None:
    decision = decide(Actor(membership.user_id, membership.role), action)
    if not decision:
        assert decision.denial is not None
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=decision.denial.value)


def _read(file: UploadFile) -> FieldList:
    try:
        return read_field_list(file.file.read())
    except FarmdokError as error:
        _invalid(error)


def _read_log(file: UploadFile) -> CropLog:
    try:
        return read_crop_log(file.file.read())
    except FarmdokError as error:
        _invalid(error)


def _invalid(error: FarmdokError) -> NoReturn:
    invalid = InvalidReport(
        problems=[ImportProblem(code=p.code, row=p.row, detail=p.detail) for p in error.problems]
    )
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT, detail=invalid.model_dump(mode="json")
    ) from error


def _plan(
    db: Session,
    membership: Membership,
    field_list: FieldList,
    years: set[int],
    reference_year: int | None,
    crop_assignments: str | None,
) -> FieldListPlan[Borrowed]:
    if reference_year is not None and (
        reference_year not in years or reference_year == field_list.harvest_year
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_reference_year")
    year = reference_year or nearest_year(field_list.harvest_year, years)
    try:
        assignments = _ASSIGNMENTS.validate_json(crop_assignments or "{}")
        return field_list_import.plan_import(db, membership.farm_id, field_list, year, assignments)
    except (ValidationError, InvalidCropAssignmentError) as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_crop_assignments"
        ) from error


def _resolutions(raw: str | None) -> LogResolutions:
    try:
        return _RESOLUTIONS.validate_json(raw or "{}")
    except ValidationError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_resolutions"
        ) from error


def _to_resolutions(parsed: LogResolutions) -> Resolutions:
    choices = {}
    for name, product in parsed.products.items():
        if sum((product.farm_input_id is not None, product.create, product.none)) != 1:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_resolutions")
        choices[name] = ProductChoice(farm_input_id=product.farm_input_id, create=product.create)
    return Resolutions(parsed.activities, choices, parsed.entries)


def _plan_log(
    db: Session, membership: Membership, log: CropLog, resolutions: Resolutions
) -> CropLogPlan:
    try:
        return crop_log_import.plan_import(db, membership.farm_id, log, resolutions)
    except InvalidResolutionError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_resolutions"
        ) from error


def _wgs84(geometry: Borrowed | None) -> MultiPolygon | None:
    return None if geometry is None else MultiPolygon.model_validate(json.loads(geometry.wgs84))


def _batches(
    db: Session, farm_id: uuid.UUID, batch_id: uuid.UUID | None = None
) -> list[ImportBatchOut]:
    field_count = (
        select(func.count(Field.id))
        .where(Field.import_batch_id == ImportBatch.id)
        .scalar_subquery()
    )
    plot_count = (
        select(func.count(Plot.id)).where(Plot.import_batch_id == ImportBatch.id).scalar_subquery()
    )
    task_count = (
        select(func.count(Task.id)).where(Task.import_batch_id == ImportBatch.id).scalar_subquery()
    )
    query = (
        select(ImportBatch, User.email, field_count, plot_count, task_count)
        .outerjoin(User, User.id == ImportBatch.created_by_id)
        .where(ImportBatch.farm_id == farm_id)
        .order_by(ImportBatch.harvest_year.desc(), ImportBatch.created_at.desc())
    )
    if batch_id is not None:
        query = query.where(ImportBatch.id == batch_id)
    return [
        ImportBatchOut(
            id=batch.id,
            kind=batch.kind,
            harvest_year=batch.harvest_year,
            source_name=batch.source_name,
            created_by=email,
            created_at=batch.created_at,
            field_count=fields,
            plot_count=plots,
            task_count=tasks,
        )
        for batch, email, fields, plots, tasks in db.execute(query)
    ]
