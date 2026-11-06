"""Farm Inputs: the fertilisers, seed and other inputs Operations refer to.

Everyone on the Farm reads them; Admins and Workers keep them. An input that past records
refer to is archived, never deleted.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Self

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from cropstar_api import farm_input_catalogue
from cropstar_api.db import Db
from cropstar_api.farms import FarmMembership
from cropstar_api.land_use import land_use_names
from cropstar_api.models import (
    FarmInput,
    FarmInputKind,
    FarmInputUnit,
    Membership,
    Operation,
    Task,
    ValueSource,
)
from cropstar_api.policy import Action, Actor, decide

router = APIRouter(prefix="/farms/{farm_id}", tags=["farm inputs"])

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
# kg per unit: a tonne of manure holds a few kg, 100 kg of mineral fertiliser at most 100.
Content = Annotated[Decimal, Field(ge=0, le=1000, max_digits=8, decimal_places=3)]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]

_FERTILISER_FIELDS = (
    "unit",
    "dry_matter_percent",
    "total_n",
    "available_n",
    "p2o5",
    "k2o",
    "value_source",
    "source_reference",
    "analysed_on",
    "catalogue_entry",
)
_NUTRIENTS = ("dry_matter_percent", "total_n", "available_n", "p2o5", "k2o")
_SEED_FIELDS = ("land_use_code", "variety", "thousand_kernel_weight_g")


# ── Schemas ─────────────────────────────────────────────────────────────────


class FarmInputBody(BaseModel):
    """A Farm Input as entered. Fertilisers carry a unit and contents per unit with their
    source; seed carries a Land Use. Fields of another kind are refused."""

    name: Name
    note: Text | None = None
    unit: FarmInputUnit | None = None
    dry_matter_percent: Percent | None = None
    total_n: Content | None = None
    # Plant-available N in the year of application.
    available_n: Content | None = None
    p2o5: Content | None = None
    k2o: Content | None = None
    value_source: ValueSource | None = None
    source_reference: Reference | None = None
    # When the sample was analysed; required for lab analyses.
    analysed_on: date | None = None
    # The catalogue entry the values were started from.
    catalogue_entry: str | None = None
    land_use_code: str | None = None
    variety: Name | None = None
    thousand_kernel_weight_g: (
        Annotated[Decimal, Field(gt=0, le=2000, max_digits=6, decimal_places=2)] | None
    ) = None

    @field_validator("note", "source_reference")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def _plausible(self) -> Self:
        n, available = self.total_n, self.available_n
        if n is not None and available is not None and available > n:
            raise ValueError("plant-available N cannot exceed total N")
        if self.value_source is ValueSource.LAB_ANALYSIS and self.analysed_on is None:
            raise ValueError("a lab analysis needs its date")
        if (
            self.catalogue_entry is not None
            and farm_input_catalogue.entry(self.catalogue_entry) is None
        ):
            raise ValueError("unknown catalogue entry")
        if self.land_use_code is not None and self.land_use_code not in land_use_names():
            raise ValueError("unknown Land Use code")
        return self


class FarmInputCreate(FarmInputBody):
    kind: FarmInputKind


class FarmInputOut(BaseModel):
    id: uuid.UUID
    kind: FarmInputKind
    name: str
    note: str | None
    unit: FarmInputUnit | None
    dry_matter_percent: float | None
    total_n: float | None
    available_n: float | None
    p2o5: float | None
    k2o: float | None
    value_source: ValueSource | None
    source_reference: str | None
    analysed_on: date | None
    catalogue_entry: str | None
    land_use_code: str | None
    land_use_name: str | None
    variety: str | None
    thousand_kernel_weight_g: float | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    # Whether Operations refer to it: then it can be archived but not deleted.
    in_use: bool


class CatalogueEntryOut(BaseModel):
    code: str
    name: str
    unit: FarmInputUnit
    dry_matter_percent: float | None
    total_n: float | None
    available_n: float | None
    p2o5: float | None
    k2o: float | None
    # Publication, edition and table the values come from.
    source: str


class LandUseOut(BaseModel):
    code: str
    name: str


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/farm-inputs", operation_id="listFarmInputs")
def list_farm_inputs(
    membership: FarmMembership,
    db: Db,
    kind: Annotated[FarmInputKind | None, Query()] = None,
    archived: Annotated[
        bool | None, Query(description="Only archived (true) or only current (false) inputs")
    ] = None,
) -> list[FarmInputOut]:
    query = select(FarmInput).where(FarmInput.farm_id == membership.farm_id)
    if kind is not None:
        query = query.where(FarmInput.kind == kind)
    if archived is not None:
        query = query.where(
            FarmInput.archived_at.is_not(None) if archived else FarmInput.archived_at.is_(None)
        )
    inputs = list(db.scalars(query.order_by(FarmInput.kind, FarmInput.name)))
    used = _in_use(db, membership.farm_id)
    return [_out(item, item.id in used) for item in inputs]


@router.post("/farm-inputs", operation_id="createFarmInput", status_code=status.HTTP_201_CREATED)
def create_farm_input(body: FarmInputCreate, membership: FarmMembership, db: Db) -> FarmInputOut:
    _require_permission(membership)
    now = datetime.now(UTC)
    item = FarmInput(farm_id=membership.farm_id, kind=body.kind, created_at=now, updated_at=now)
    _apply(item, body)
    db.add(item)
    db.flush()
    return _out(item, False)


@router.get("/farm-inputs/{input_id}", operation_id="getFarmInput")
def read_farm_input(input_id: uuid.UUID, membership: FarmMembership, db: Db) -> FarmInputOut:
    item = _get(db, membership, input_id)
    return _out(item, item.id in _in_use(db, membership.farm_id))


@router.put("/farm-inputs/{input_id}", operation_id="updateFarmInput")
def update_farm_input(
    input_id: uuid.UUID, body: FarmInputBody, membership: FarmMembership, db: Db
) -> FarmInputOut:
    """Replaces everything but the kind, e.g. with the values of a new lab analysis."""
    _require_permission(membership)
    item = _get(db, membership, input_id)
    _apply(item, body)
    item.updated_at = datetime.now(UTC)
    return _out(item, item.id in _in_use(db, membership.farm_id))


@router.post("/farm-inputs/{input_id}/archive", operation_id="archiveFarmInput")
def archive_farm_input(input_id: uuid.UUID, membership: FarmMembership, db: Db) -> FarmInputOut:
    """No longer offered for new Operations; past records keep showing it."""
    _require_permission(membership)
    item = _get(db, membership, input_id)
    item.archived_at = item.archived_at or datetime.now(UTC)
    return _out(item, item.id in _in_use(db, membership.farm_id))


@router.post("/farm-inputs/{input_id}/restore", operation_id="restoreFarmInput")
def restore_farm_input(input_id: uuid.UUID, membership: FarmMembership, db: Db) -> FarmInputOut:
    _require_permission(membership)
    item = _get(db, membership, input_id)
    item.archived_at = None
    return _out(item, item.id in _in_use(db, membership.farm_id))


@router.delete(
    "/farm-inputs/{input_id}",
    operation_id="deleteFarmInput",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_farm_input(input_id: uuid.UUID, membership: FarmMembership, db: Db) -> None:
    """Only for inputs nothing refers to; archive the others."""
    _require_permission(membership)
    item = _get(db, membership, input_id)
    if item.id in _in_use(db, membership.farm_id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="farm_input_in_use")
    db.delete(item)


@router.get("/farm-input-catalogue", operation_id="listFarmInputCatalogue")
def list_catalogue(membership: FarmMembership) -> list[CatalogueEntryOut]:
    """Standard nutrient contents of farm manure, each with its source and edition."""
    return [
        CatalogueEntryOut(
            code=e.code,
            name=e.name,
            unit=e.unit,
            dry_matter_percent=_float(e.dry_matter_percent),
            total_n=_float(e.total_n),
            available_n=_float(e.available_n),
            p2o5=_float(e.p2o5),
            k2o=_float(e.k2o),
            source=e.source,
        )
        for e in farm_input_catalogue.catalogue()
    ]


@router.get("/land-uses", operation_id="listLandUses")
def list_land_uses(membership: FarmMembership) -> list[LandUseOut]:
    """AMA Land Use codes and names, for choosing what seed is for."""
    return [LandUseOut(code=code, name=name) for code, name in land_use_names().items()]


# ── Helpers ─────────────────────────────────────────────────────────────────


def _require_permission(membership: Membership) -> None:
    decision = decide(Actor(membership.user_id, membership.role), Action.MANAGE_FARM_INPUTS)
    if not decision:
        assert decision.denial is not None
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=decision.denial.value)


def _get(db: Session, membership: Membership, input_id: uuid.UUID) -> FarmInput:
    item = db.get(FarmInput, input_id)
    if item is None or item.farm_id != membership.farm_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="farm_input_not_found")
    return item


def _apply(item: FarmInput, body: FarmInputBody) -> None:
    def given(names: tuple[str, ...]) -> bool:
        return any(getattr(body, name) is not None for name in names)

    if item.kind is not FarmInputKind.FERTILISER and given(_FERTILISER_FIELDS):
        _invalid("fertiliser_fields_not_allowed")
    if item.kind is not FarmInputKind.SEED and given(_SEED_FIELDS):
        _invalid("seed_fields_not_allowed")
    if item.kind is FarmInputKind.FERTILISER:
        if body.unit is None:
            _invalid("unit_required")
        # Product rule: no number without its source.
        if given(_NUTRIENTS) and body.value_source is None:
            _invalid("value_source_required")
    if item.kind is FarmInputKind.SEED and body.land_use_code is None:
        _invalid("land_use_required")

    item.name = body.name
    item.note = body.note
    for name in (*_FERTILISER_FIELDS, *_SEED_FIELDS):
        setattr(item, name, getattr(body, name))
    item.land_use_name = land_use_names()[body.land_use_code] if body.land_use_code else None


def _invalid(code: str) -> None:
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=code)


def _in_use(db: Session, farm_id: uuid.UUID) -> set[uuid.UUID]:
    """Farm Inputs that Planned or Actual Details refer to."""
    referenced = [
        select(Task.planned_details["farm_input_id"].astext).where(Task.farm_id == farm_id),
        select(Operation.planned_details["farm_input_id"].astext)
        .join(Task, Task.id == Operation.task_id)
        .where(Task.farm_id == farm_id),
        select(Operation.actual_details["farm_input_id"].astext)
        .join(Task, Task.id == Operation.task_id)
        .where(Task.farm_id == farm_id),
    ]
    found: set[uuid.UUID] = set()
    for query in referenced:
        column = query.selected_columns[0]
        for value in db.scalars(query.where(column.is_not(None))):
            try:
                found.add(uuid.UUID(value))
            except ValueError:
                continue
    return found


def _float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _out(item: FarmInput, in_use: bool) -> FarmInputOut:
    return FarmInputOut(
        id=item.id,
        kind=item.kind,
        name=item.name,
        note=item.note,
        unit=item.unit,
        dry_matter_percent=_float(item.dry_matter_percent),
        total_n=_float(item.total_n),
        available_n=_float(item.available_n),
        p2o5=_float(item.p2o5),
        k2o=_float(item.k2o),
        value_source=item.value_source,
        source_reference=item.source_reference,
        analysed_on=item.analysed_on,
        catalogue_entry=item.catalogue_entry,
        land_use_code=item.land_use_code,
        land_use_name=item.land_use_name,
        variety=item.variety,
        thousand_kernel_weight_g=_float(item.thousand_kernel_weight_g),
        created_at=item.created_at,
        updated_at=item.updated_at,
        archived_at=item.archived_at,
        in_use=in_use,
    )
