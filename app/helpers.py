import math
from typing import Sequence

import pyproj
from geojson import Feature
from geoalchemy2.shape import to_shape
from shapely.geometry import Point
from shapely.ops import transform

from app import app
from app.schemas import RouteSchema
from app.models import Route


route_schema = RouteSchema()
_project = pyproj.Transformer.from_crs(4326, app.config['PROJECTION'], always_xy=True).transform
_to_wgs84 = pyproj.Transformer.from_crs(app.config['PROJECTION'], 4326, always_xy=True).transform


def project(shape):
    """Project spherical coordinates."""
    return shape if shape.is_empty else transform(_project, shape)


def to_wgs84(shape):
    "Transform planar coordinates to spherical (WGS84)."
    return shape if shape.is_empty else transform(_to_wgs84, shape)


def parse_lat_lon(lat_lon: str) -> Point:
    """Convert coordinates passed as a query parameter to a list."""
    project(Point(map(float, lat_lon.split(',')[::-1])))


def haversine(from_: Sequence, to_: Sequence) -> float:
    """Computes distance on a sphere between two points."""
    from_lat, from_lon, to_lat, to_lon = map(math.radians, [*from_, *to_])
    a = (
        math.sin((from_lat - to_lat)/2)**2 +
        math.cos(from_lat) * math.cos(to_lat) *
        math.sin((from_lon-to_lon)/2)**2
    )
    return 6371 * 2 * math.asin(math.sqrt(a)) * 1000  # in meters


def route_to_feature(route: Route) -> Feature:
    """Convert a PostGIS route record to GeoJSON."""
    return Feature(route.id, to_wgs84(to_shape(route.geom)), route_schema.dump(route))
