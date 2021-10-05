import math

import pyproj
from geojson import Feature
from geoalchemy2.shape import to_shape
from shapely.geometry import Polygon

from app import app
from app.schemas import RouteSchema


route_schema = RouteSchema()
transform = pyproj.Transformer.from_crs(4326, app.config['PROJECTION'], always_xy=True).transform


# These two functions transform a.k.a reproject geographic coords to planar
# Although most of the code is repeated, I chose to keep them separate so their
# signature be more 'clear' (no direction parameter, just two obviously named funcs)

def project(shape):
    if shape.is_empty:
        return shape
    geometry_type = type(shape)
    if isinstance(shape, Polygon):
        shape = shape.exterior
    xx, yy = transform(*shape.xy, direction='FORWARD')
    return geometry_type(zip(xx.tolist(), yy.tolist()))


def to_wgs84(shape):
    if shape.is_empty:
        return shape
    geometry_type = type(shape)
    if isinstance(shape, Polygon):
        shape = shape.exterior
    xx, yy = transform(*shape.xy, direction='INVERSE')
    return geometry_type(zip(xx.tolist(), yy.tolist()))


def haversine(from_, to_):
    from_lat, from_lon, to_lat, to_lon = map(math.radians, [*from_, *to_])
    a = math.sin((from_lat - to_lat)/2)**2 + math.cos(from_lat) * math.cos(to_lat) * math.sin((from_lon-to_lon)/2)**2
    return 6371 * 2 * math.asin(math.sqrt(a)) * 1000  # in meters


def route_to_feature(route):
    return Feature(route.id, to_wgs84(to_shape(route.geom)), route_schema.dump(route))
