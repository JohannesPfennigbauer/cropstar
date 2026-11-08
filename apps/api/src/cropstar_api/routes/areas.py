"""Fields and Plots per Harvest Year, as GeoJSON in WGS84."""

import json
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Select, func, select

from cropstar_api import plot_lineage
from cropstar_api.db import Db
from cropstar_api.farms import FarmMembership
from cropstar_api.geometry import to_wgs84_geojson
from cropstar_api.land_use import LandUseCategory, land_use_category
from cropstar_api.models import AreaSource, Field, Plot

router = APIRouter(prefix="/farms/{farm_id}", tags=["areas"])

HarvestYear = Annotated[int, Query(ge=1990, le=2200)]
Position = tuple[float, float]


class MultiPolygon(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: list[list[list[Position]]]


class AreaProvenance(BaseModel):
    """Where the geometry came from and when it arrived."""

    source: AreaSource
    imported_at: datetime
    # For borrowed geometry: the Harvest Year it comes from.
    borrowed_from_year: int | None


class FieldRef(BaseModel):
    id: uuid.UUID
    number: int
    name: str | None


class FieldProperties(BaseModel):
    id: uuid.UUID
    harvest_year: int
    number: int
    name: str | None
    land_use_code: str
    land_use_name: str
    declared_area_ha: float
    plot_count: int
    provenance: AreaProvenance


class FieldFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: uuid.UUID
    # Null when the geometry is not known (source "none").
    geometry: MultiPolygon | None
    properties: FieldProperties


class FieldCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[FieldFeature]


class PlotProperties(BaseModel):
    id: uuid.UUID
    harvest_year: int
    number: int
    name: str | None
    land_use_code: str
    land_use_name: str
    land_use_category: LandUseCategory
    declared_area_ha: float
    field: FieldRef
    provenance: AreaProvenance


class PlotFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: uuid.UUID
    geometry: MultiPolygon | None
    properties: PlotProperties


class PlotCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[PlotFeature]


@router.get("/fields", operation_id="listFields")
def list_fields(membership: FarmMembership, db: Db, harvest_year: HarvestYear) -> FieldCollection:
    plot_count = select(func.count(Plot.id)).where(Plot.field_id == Field.id).scalar_subquery()
    rows = db.execute(
        select(Field, to_wgs84_geojson(Field.geometry), plot_count)
        .where(Field.farm_id == membership.farm_id, Field.harvest_year == harvest_year)
        .order_by(Field.number)
    ).all()
    return FieldCollection(
        features=[
            FieldFeature(
                id=field.id,
                geometry=parse_geometry(geometry),
                properties=FieldProperties(
                    id=field.id,
                    harvest_year=field.harvest_year,
                    number=field.number,
                    name=field.name,
                    land_use_code=field.land_use_code,
                    land_use_name=field.land_use_name,
                    declared_area_ha=float(field.declared_area_ha),
                    plot_count=count,
                    provenance=_provenance(field),
                ),
            )
            for field, geometry, count in rows
        ]
    )


@router.get("/plots", operation_id="listPlots")
def list_plots(membership: FarmMembership, db: Db, harvest_year: HarvestYear) -> PlotCollection:
    rows = db.execute(
        _plots(membership.farm_id)
        .where(Field.harvest_year == harvest_year)
        .order_by(Field.number, Plot.number)
    ).all()
    return PlotCollection(features=[_plot_feature(plot, field, geo) for plot, field, geo in rows])


@router.get("/plots/{plot_id}", operation_id="getPlot")
def read_plot(membership: FarmMembership, db: Db, plot_id: uuid.UUID) -> PlotFeature:
    row = db.execute(_plots(membership.farm_id).where(Plot.id == plot_id)).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="plot_not_found")
    plot, field, geometry = row
    return _plot_feature(plot, field, geometry)


class EarlierPlotOut(BaseModel):
    """A Plot of an earlier Harvest Year on the same ground."""

    id: uuid.UUID
    harvest_year: int
    field_number: int
    plot_number: int
    land_use_code: str
    land_use_name: str
    land_use_category: LandUseCategory
    # Share of the asking Plot's area this earlier Plot covers, from 0 to 1.
    overlap: float


@router.get("/plots/{plot_id}/lineage", operation_id="getPlotLineage")
def read_plot_lineage(
    membership: FarmMembership, db: Db, plot_id: uuid.UUID
) -> list[EarlierPlotOut]:
    """The Plot's Predecessors and theirs, back through all earlier Harvest Years, newest year
    first. Within a year, the Plot covering most of this one comes first."""
    return [
        EarlierPlotOut(
            id=p.id,
            harvest_year=p.harvest_year,
            field_number=p.field_number,
            plot_number=p.plot_number,
            land_use_code=p.land_use_code,
            land_use_name=p.land_use_name,
            land_use_category=land_use_category(p.land_use_code),
            overlap=p.overlap,
        )
        for p in plot_lineage.lineage(db, membership.farm_id, plot_id)
    ]


def _plots(farm_id: uuid.UUID) -> Select[Plot, Field, str | None]:
    return (
        select(Plot, Field, to_wgs84_geojson(Plot.geometry))
        .join(Field, Plot.field_id == Field.id)
        .where(Field.farm_id == farm_id)
    )


def parse_geometry(geojson: str | None) -> MultiPolygon | None:
    return None if geojson is None else MultiPolygon.model_validate(json.loads(geojson))


def _plot_feature(plot: Plot, field: Field, geometry: str | None) -> PlotFeature:
    return PlotFeature(
        id=plot.id,
        geometry=parse_geometry(geometry),
        properties=PlotProperties(
            id=plot.id,
            harvest_year=field.harvest_year,
            number=plot.number,
            name=plot.name,
            land_use_code=plot.land_use_code,
            land_use_name=plot.land_use_name,
            land_use_category=land_use_category(plot.land_use_code),
            declared_area_ha=float(plot.declared_area_ha),
            field=FieldRef(id=field.id, number=field.number, name=field.name),
            provenance=_provenance(plot),
        ),
    )


def _provenance(area: Field | Plot) -> AreaProvenance:
    return AreaProvenance(
        source=area.geometry_source,
        imported_at=area.imported_at,
        borrowed_from_year=area.borrowed_from_year,
    )
