import math

import pyproj
from geojson import Feature
from geoalchemy2.shape import to_shape

from app.schemas import RouteSchema


route_schema = RouteSchema()
PROJECTION = 32637  # https://epsg.io/32637
TRANSFORM = pyproj.Transformer.from_crs(4326, PROJECTION, always_xy=True)


def transform(shape, to_wgs84=False):
    if shape.is_empty:
        return shape
    geometry_type = type(shape)
    direction = 'INVERSE' if to_wgs84 else 'FORWARD'
    xx, yy = TRANSFORM.transform(*shape.xy, direction=direction)
    return geometry_type(zip(xx.tolist(), yy.tolist()))


def haversine(from_, to_):
    from_lat, from_lon, to_lat, to_lon = map(math.radians, [*from_, *to_])
    a = math.sin((from_lat - to_lat)/2)**2 + math.cos(from_lat) * math.cos(to_lat) * math.sin((from_lon-to_lon)/2)**2
    return 6371 * 2 * math.asin(math.sqrt(a)) * 1000  # in meters


def route_to_feature(route):
    return Feature(route.id, to_shape(route.geog), route_schema.dump(route))
