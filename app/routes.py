from uuid import uuid4

import numpy as np
import pyproj
import sqlalchemy
from shapely.geometry import Point, LineString, MultiPoint
from shapely.ops import nearest_points, substring, snap, linemerge, unary_union
from geojson import Feature, FeatureCollection
from flask import request
from geoalchemy2.shape import to_shape
from openrouteservice.exceptions import ApiError

from app import app, db, ors
from app.models import Route, PickupPoint


st_distance = sqlalchemy.func.ST_Distance
POINT_PROXIMITY_THRESHOLD = 1000
MAX_PREPARED_ROUTES = 5
TRANSFORM = pyproj.Transformer.from_crs(4326, 32637, always_xy=True)
ROUTE_NOT_FOUND_MESSAGE = 'No such route in the database :-('


def transform(shape, to_wgs84=False):
    if shape.is_empty:
        return shape
    geometry_type = type(shape)
    direction = 'INVERSE' if to_wgs84 else 'FORWARD'
    xx, yy = TRANSFORM.transform(*shape.xy, direction=direction)
    return geometry_type(zip(xx.tolist(), yy.tolist()))


def healthcheck():
    return {'status': 'OK'}


def get_pickup_point(point_id):
    point = PickupPoint.query.get_or_404(point_id, 'No such pick-up point in the database :-(')
    return list(to_shape(point.geom).coords[0])


def post_pickup_point():
    geom = Point(request.json['position'][::-1]).wkt
    route_id = request.json['route_id']
    route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    if route.profile == 'driving-car':
        return 'Only passenger routes can have pick-up points', 400
    point = PickupPoint.query.filter(PickupPoint.route_id == route_id).first()
    if point:
        point.geom = geom
    else:
        point = PickupPoint(id=uuid4(), geom=geom, route_id=route_id)
        db.session.add(point)
    db.session.commit()
    return point.id, 201


def is_at_pickup_point(route_id, position):
    point = PickupPoint.query.filter(PickupPoint.route_id == route_id).first_or_404(f'Route {route_id} has no pick-up point')
    driver_position = transform(Point(map(float, position.split(',')[::-1])))
    return driver_position.distance(transform(to_shape(point.geom))) < app.config['PICKUP_POINT_PROXIMITY_THRESHOLD']


def immitate(route_id):
    route = transform(to_shape(Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).route))
    route_coords = np.array(route.coords)
    route_coords_delta = np.random.uniform(-20.0, 20.0, (len(route_coords), 2))
    route_coords += route_coords_delta
    points = [transform(Point(position[::-1])) for position in request.json['positions']]
    route_vertices = MultiPoint(route_coords)
    points_snapped = [nearest_points(route_vertices, point)[0].coords[0] for point in points]
    for new, old in zip(points, points_snapped):
        route_coords = np.where(route_coords == old, new, route_coords)
    return Feature(geometry=transform(LineString(route_coords), to_wgs84=True))


def remainder(route_id, position):
    driver_route = to_shape(Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).route)
    current_position = Point(map(float, position.split(',')[::-1]))
    current_position_snapped = nearest_points(driver_route, current_position)[0]
    route_passed_fraction = driver_route.project(current_position_snapped, normalized=True)
    remaining_route = substring(driver_route, route_passed_fraction, 1, normalized=True)
    return list(remaining_route.coords)


def suggest_pickup(route_id, position):
    driver_route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    driver_route_projected = transform(to_shape(driver_route.route))
    passenger_start_wgs84 = Point(map(float, position.split(',')[::-1]))
    passenger_start_projected = transform(passenger_start_wgs84)
    # Identify the closest point on the driver's route
    nearest_point = nearest_points(driver_route_projected, passenger_start_projected)[0]
    # Obtain the actual (graph-based route) so that the pickup point always be accessible
    passenger_route = ors.directions(
        [pt.coords[0] for pt in (passenger_start_wgs84, transform(nearest_point, to_wgs84=True))],
        'foot-walking'
    )[0]
    try:
        # If straight-line nearest point was unreachable by walking, resulting route may contain a new 'nearest' point
        nearest_point = passenger_route['geometry'][-1]
        if driver_route_projected.project(transform(Point(nearest_point))) < 500:
            radius = 0
            nearest_point = to_shape(driver_route.start).coords[0]
            passenger_route = ors.directions([passenger_start_wgs84.coords[0], nearest_point], 'foot-walking')[0]
        else:
            # Calculate the straight-line distance for the front to use as the circle radius
            radius = passenger_start_projected.distance(transform(Point(nearest_point)))
        return {
            'point': nearest_point,
            'radius': round(radius, 2),
            'distance': passenger_route['distance']
        }
    except IndexError:
        return {}


def directions():
    """"""
    prepared_routes, handles = [], []
    # Convert start, end and intermediate points from [lat, lon] to [lon, lat] format used in ORS & Shapely
    positions = [position[::-1] for position in request.json['positions']]
    if len(set(str(position) for position in positions)) != len(positions):
        return 'Request contains duplicate positions', 400
    with_alternatives = request.json.get('alternatives', True) and len(positions) == 2
    with_handles = request.json.get('handles', True)
    # Start & end will mostly be manipulated via Shapely, so turn them into shapes
    start, finish = Point(positions[0]), Point(positions[1])
    # Reproject them to be used with Shapely (leave the spherical versions to save to the DB later)
    start_projected, finish_projected = transform(start), transform(finish)
    # Order intermediate positions along the route
    if len(positions) > 2:
        positions.sort(key=lambda x: start_projected.distance(transform(Point(x))))
    # Routing using existing routes
    from_route_id, to_route_id = request.json.get('from_route_id'), request.json.get('to_route_id')
    from_route = to_shape(
        Route.query.get_or_404(from_route_id, ROUTE_NOT_FOUND_MESSAGE).route
    ) if from_route_id else None
    to_route = to_shape(
        Route.query.get_or_404(to_route_id, ROUTE_NOT_FOUND_MESSAGE).route
    ) if to_route_id else None
    if from_route and to_route:
        from_point, to_point = [point.coords[0] for point in nearest_points(from_route, to_route)]
        positions = [from_point, *positions, to_point]
    elif from_route:
        nearest_point = nearest_points(from_route, start)[0]
        positions.insert(0, nearest_point.coords[0])
    elif to_route:
        nearest_point = nearest_points(to_route, start)[0]
        positions.append(nearest_point.coords[0])
    # Check if there are similar routes in the user's history; if there are any, return them along w/ the new ones
    if with_alternatives:
        # Get all the routes from the user's history
        past_routes = Route.query.filter(Route.trip_id != None, Route.user_id == request.json['user_id']).all()
        # Filter out those whose start & finish were close enough to the currently requested ones
        similar_routes = [
            {'geometry': to_shape(route.route), 'distance': route.distance, 'duration': route.duration}
            for route in past_routes
            if transform(to_shape(route.start)).distance(start_projected) < POINT_PROXIMITY_THRESHOLD
            and transform(to_shape(route.finish)).distance(finish_projected) < POINT_PROXIMITY_THRESHOLD
        ]
        for route in similar_routes[:MAX_PREPARED_ROUTES]:
            route_geom = transform(LineString(route['geometry']))
            # Get the closest points on the past route to counterparts requested by the user
            nearest_to_start, _ = nearest_points(route_geom, start_projected)
            nearest_to_finish, _ = nearest_points(route_geom, finish_projected)
            # Reproject them back to WGS84 for the ORS
            nearest_to_start_4326 = transform(nearest_to_start, to_wgs84=True).coords[0]
            nearest_to_finish_4326 = transform(nearest_to_finish, to_wgs84=True).coords[0]
            # Get the routes between the user's requested points and those closest to them on the past route
            # A tail is from the start to the point closest to the start, a head - likewise but from the finish
            empty_route = {'geometry': [], 'distance': 0, 'duration': 0}
            try:
                tail = ors.directions([positions[0], nearest_to_start_4326], request.json['profile'])[0]
                head = ors.directions([nearest_to_finish_4326, positions[-1]], request.json['profile'])[0]
            except ApiError as e:
                return str(e), 500
            for part in (tail, head):
                part = empty_route if len(part['geometry']) < 2 else part
            tail_geom, head_geom = [transform(LineString(part['geometry']).simplify(0)) for part in (tail, head)]
            # Extract the relevant part of the past route
            cut_point_distances = [route_geom.project(pt) for pt in (nearest_to_start, nearest_to_finish)]
            common_part = substring(route_geom, *cut_point_distances)
            # Remove duplicate segments
            if tail['geometry']:
                tail_snapped = LineString([
                    snap(Point(coords), nearest_points(common_part, Point(coords))[0], 25)
                    for coords in tail_geom.coords
                ])
                if tail_snapped.overlaps(common_part):
                    tail_geom, common_part = tail_snapped.symmetric_difference(common_part)
                elif tail_snapped.within(common_part):
                    tail_geom = LineString()
            if head['geometry']:
                head_snapped = LineString([
                    snap(Point(coords), nearest_points(common_part, Point(coords))[0], 25)
                    for coords in head_geom.coords
                ])
                if head_snapped.overlaps(common_part):
                    head_geom, common_part = head_snapped.symmetric_difference(common_part)
                elif head_snapped.within(common_part):
                    head_geom = LineString()
            # Stitch them together
            parts_to_merge = list(filter(bool, (tail_geom, common_part, head_geom)))
            full_route = linemerge(unary_union(parts_to_merge)) if len(parts_to_merge) > 1 else common_part
            prepared_routes.append({
                'geometry': transform(full_route, to_wgs84=True).coords,
                'distance': sum([part['distance'] for part in (route, tail, head)]),
                'duration': sum([part['duration'] for part in (route, tail, head)])
            })
    # User may opt to drive ad-hoc w/out preparing a route; if make_route is False, only the end points will be saved
    if request.json.get('make_route') is False:
        route_id = uuid4()
        db.session.add(Route(
            id=route_id,
            user_id=request.json['user_id'],
            profile=request.json['profile'],
            start=start.wkt,
            finish=finish.wkt
        ))
        routes = FeatureCollection([Feature(id=route_id, geometry=LineString([start, finish]))])
    else:
        try:
            routes = ors.directions(positions, request.json['profile'], with_alternatives)
        except ApiError as e:
            return str(e), 500
        # Save routes to DB
        all_routes = routes + prepared_routes
        route_ids = [uuid4() for _ in all_routes]
        for route, route_id in zip(all_routes, route_ids):
            db.session.add(Route(
                id=route_id,
                user_id=request.json['user_id'],
                profile=request.json['profile'],
                route=LineString(route['geometry']).wkt,
                start=start.wkt,
                finish=finish.wkt,
                distance=route['distance'],
                duration=route['duration']
            ))
        if request.json['profile'] == 'driving-car' and with_handles:
            # Get midpoints of the route's last segment for the user to drag on the screen
            try:
                routes_last_parts = routes if with_alternatives else ors.directions(positions[-2:], request.json['profile'])
            except ApiError as e:
                return str(e), 500
            routes_last_parts = [route['geometry'] for route in routes_last_parts]
            handles = [LineString(route).interpolate(0.5, normalized=True) for route in routes_last_parts]
            handles = [Point(handle.coords[0]) for handle in handles]
            handles = FeatureCollection([Feature(route_id, handle) for route_id, handle in zip(route_ids, handles)])
        # Prepare the response
        routes, prepared_routes = [
            FeatureCollection([
                Feature(
                    id=route_id,
                    geometry=LineString(route['geometry']),
                    properties={attr: route[attr] for attr in ('distance', 'duration')}
                ) for route_id, route in zip(route_ids, route_set)
            ]) for route_set in (routes, prepared_routes)
        ]
    db.session.commit()
    return {
        'routes': routes,
        'handles': handles if with_handles else [],
        'prepared_routes': prepared_routes if with_alternatives else [],
    }


def get_route(route_id, full=True):
    route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    is_full = bool(route.route) and full
    route = to_shape(route.route) if is_full else LineString([
        to_shape(pt).coords[0] for pt in (route.start, route.finish)
    ])
    return {'route': Feature(id=route_id, geometry=route), 'full': is_full}


def delete_discarded_routes(route_id, user_id):
    trip_id = request.json['trip_id']
    try:
        count = Route.query.filter(Route.user_id == user_id, Route.id != route_id, Route.trip_id == None).delete()
        if count == 0:
            return 'User and route combination not found', 404
        Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).trip_id = trip_id
        db.session.commit()
    except sqlalchemy.exc.IntegrityError as e:
        db.session.rollback()
        return 'Such trip id already exists in the database', 400
    except Exception as e:
        db.session.rollback()
        return e, 500


def get_candidates(route_id):
    target_route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    candidate_route_ids = request.json['candidate_route_ids']
    candidate_routes = Route.query.filter(
        Route.id.in_(candidate_route_ids),
        Route.user_id != target_route.user_id,
        st_distance(Route.start, target_route.route) < 30000,
        st_distance(Route.finish, target_route.route) < 30000,
        st_distance(Route.finish, target_route.finish) < st_distance(Route.start, target_route.finish)
    )
    if target_route.profile == 'foot-walking':
        candidate_routes = candidate_routes.filter(Route.trip_id != None)
    # Define attributes & weights for sorting: (candidate_route, target_route, weight)
    sortings = {
        'driving-car': (
            ('start', 'start', .35),
            ('finish', 'finish', .35),
            ('start', 'route', .15),
            ('finish', 'route', .15)
        ),
        'foot-walking': (
            ('start', 'start', .35),
            ('finish', 'finish', .35),
            ('route', 'start', .15),
            ('route', 'finish', .15)
        )
    }
    candidate_routes.order_by(sum([
        st_distance(getattr(Route, candidate_attr), getattr(target_route, target_attr)) * weight
        for candidate_attr, target_attr, weight in sortings[target_route.profile]
    ]))
    return [route.id for route in candidate_routes]


def geocode(text):
    return ors.geocode(text) or 'Nothing found; try a different text', 404


def reverse_geocode(position):
    position = map(float, position.split(','))
    return ors.reverse_geocode(position) or ('Nothing found', 404)


def suggest(text):
    result = ors.suggest(text)
    return FeatureCollection(
        [Feature(geometry=feature['geometry'], properties=feature['properties']) for feature in result]
    ) if result else 'Nothing found; try a different text', 404
