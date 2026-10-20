"""Fields and Plots per Harvest Year, as GeoJSON in WGS84."""

import json
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Select, func, select

from cropstar_api.db import Db
from cropstar_api.farms import FarmMembership
from cropstar_api.land_use import LandUseCategory, land_use_category
from cropstar_api.models import Field, Plot

router = APIRouter(prefix="/farms/{farm_id}", tags=["areas"])

HarvestYear = Annotated[int, Query(ge=1990, le=2200)]
Position = tuple[float, float]
# Roughly a centimetre at Austrian latitudes; finer digits are noise.
COORDINATE_DECIMALS = 7


class MultiPolygon(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: list[list[list[Position]]]


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


class FieldFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: uuid.UUID
    geometry: MultiPolygon
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


class PlotFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: uuid.UUID
    geometry: MultiPolygon
    properties: PlotProperties


class PlotCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[PlotFeature]


@router.get("/fields", operation_id="listFields")
def list_fields(membership: FarmMembership, db: Db, harvest_year: HarvestYear) -> FieldCollection:
    plot_count = select(func.count(Plot.id)).where(Plot.field_id == Field.id).scalar_subquery()
    rows = db.execute(
        select(Field, _wgs84(Field.geometry), plot_count)
        .where(Field.farm_id == membership.farm_id, Field.harvest_year == harvest_year)
        .order_by(Field.number)
    ).all()
    return FieldCollection(
        features=[
            FieldFeature(
                id=field.id,
                geometry=MultiPolygon.model_validate(json.loads(geometry)),
                properties=FieldProperties(
                    id=field.id,
                    harvest_year=field.harvest_year,
                    number=field.number,
                    name=field.name,
                    land_use_code=field.land_use_code,
                    land_use_name=field.land_use_name,
                    declared_area_ha=float(field.declared_area_ha),
                    plot_count=count,
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


def _wgs84(geometry: Any) -> Any:
    return func.ST_AsGeoJSON(func.ST_Transform(geometry, 4326), COORDINATE_DECIMALS)


def _plots(farm_id: uuid.UUID) -> Select[Plot, Field, str]:
    return (
        select(Plot, Field, _wgs84(Plot.geometry))
        .join(Field, Plot.field_id == Field.id)
        .where(Field.farm_id == farm_id)
    )


def _plot_feature(plot: Plot, field: Field, geometry: str) -> PlotFeature:
    return PlotFeature(
        id=plot.id,
        geometry=MultiPolygon.model_validate(json.loads(geometry)),
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
        ),
    )
