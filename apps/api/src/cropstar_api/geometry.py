"""SQL expressions for moving area geometry between AMA's CRS and WGS84 GeoJSON."""

import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Text, bindparam, func, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from cropstar_api.models import AMA_SRID

# Roughly a centimetre at Austrian latitudes; finer digits are noise.
COORDINATE_DECIMALS = 7


def from_ama_geojson(geometry: dict[str, Any]) -> Any:
    """A (Multi)Polygon given in EPSG:31287, as a MultiPolygon ready to store."""
    return _ama_multipolygon(json.dumps(geometry))


def to_wgs84_geojson(geometry: Any) -> Any:
    return func.ST_AsGeoJSON(func.ST_Transform(geometry, 4326), COORDINATE_DECIMALS)


def ama_geojson_to_wgs84(db: Session, geometries: Sequence[dict[str, Any]]) -> list[str]:
    """Transform unsaved geometries for display, in one round trip, keeping their order."""
    if not geometries:
        return []
    texts = bindparam("geometries", [json.dumps(g) for g in geometries], type_=ARRAY(Text))
    rows = func.unnest(texts).table_valued("geometry", with_ordinality="position").render_derived()
    return list(
        db.scalars(
            select(to_wgs84_geojson(_ama_multipolygon(rows.c.geometry))).order_by(rows.c.position)
        )
    )


def _ama_multipolygon(geojson: Any) -> Any:
    return func.ST_Multi(func.ST_SetSRID(func.ST_GeomFromGeoJSON(geojson), AMA_SRID))
