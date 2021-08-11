from uuid import uuid4

import pyproj
import numpy as np
from shapely.geometry import Point, LineString, MultiPoint
from shapely.ops import nearest_points, substring, snap, linemerge, unary_union
from geojson import Feature, FeatureCollection
from flask import request, jsonify
from flask_restful import Resource, Api
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from geoalchemy2.shape import to_shape

from api import app, db, ors
from api.models import Route, PickupPoint


api = Api(app)

AVAILABLE_PROFILES = ('driving-car', 'foot-walking')
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


@app.route('/', methods=['GET'])
def healthcheck():
    return jsonify({'status': 'OK'})


@app.route('/routes/<uuid:id_>/immitate', methods=['POST'])
def immitate(id_):
    route = transform(to_shape(Route.query.get_or_404(id_).route))
    route_coords = np.array(route.coords)
    route_coords_delta = np.random.uniform(-20.0, 20.0, (len(route_coords), 2))
    route_coords += route_coords_delta
    try:
        points = [transform(Point(position[::-1])) for position in request.json['points']]
    except (TypeError, KeyError):
        return '"points" attribute must be present in the request body. If there are none, just set it to [].', 400
    route_vertices = MultiPoint(route_coords)
    points_snapped = [nearest_points(route_vertices, point)[0].coords[0] for point in points]
    for new, old in zip(points, points_snapped):
        route_coords = np.where(route_coords == old, new, route_coords)
    return jsonify(Feature(geometry=transform(LineString(route_coords), to_wgs84=True)))


class PickupPointResource(Resource):
    """"""

    def get(self, id_):
        point = PickupPoint.query.get_or_404(id_, 'No such pick-up point in the database :-(')
        return jsonify(to_shape(point.geom).coords[0])

    def post(self):
        try:
            coords = request.json['coordinates'][::-1]
            user_id = request.json['user_id']
            trip_id = request.json['trip_id']
        except KeyError:
            return 'Please provide: coordinates, user_id, trip_id', 400
        id_ = uuid4()
        db.session.add(PickupPoint(
            id=id_,
            geom=Point(coords).wkt,
            user_id=user_id,
            trip_id=trip_id
        ))
        db.session.commit()
        return jsonify(id_)


api.add_resource(PickupPointResource, '/pickup', '/pickup/<uuid:id_>')


@app.route('/routes/<uuid:route_id>/remainder', methods=['GET'])
def remainder(route_id):
    driver_route = to_shape(Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).route)
    current_position = Point(map(float, request.args.get('current_position').split(',')[::-1]))
    current_position_snapped = nearest_points(driver_route, current_position)[0]
    route_passed_fraction = driver_route.project(current_position_snapped, normalized=True)
    remaining_route = substring(driver_route, route_passed_fraction, 1, normalized=True)
    return jsonify(list(remaining_route.coords))


@app.route('/routes/<uuid:id_>/suggest_pickup', methods=['GET'])
def pickup(id_):
    # Process the arguments
    driver_route = transform(to_shape(Route.query.get_or_404(id_, ROUTE_NOT_FOUND_MESSAGE).route))
    try:
        passenger_start_wgs84 = Point(map(float, request.args['from'].split(',')[::-1]))
    except KeyError:
        return 'Please, specify a "from" location as a string <lat,lon>', 400
    passenger_start_projected = transform(passenger_start_wgs84)
    # Identify the closest point on the driver's route
    nearest_point = nearest_points(driver_route, passenger_start_projected)[0]
    # Obtain the actual (graph-based route) so that the pickup point always be accessible
    passenger_route = ors.directions(
        [pt.coords[0] for pt in (passenger_start_wgs84, transform(nearest_point, to_wgs84=True))],
        'foot-walking'
    )[0]
    try:
        # If straight-line nearest point was unreachable by walking, resulting route may contain a new 'nearest' point
        nearest_point = passenger_route['geometry'][-1]
        if driver_route.project(transform(Point(nearest_point))) < 500:
            return ''
        # Calculate the straight-line distance for the front to use as the circle radius
        radius = passenger_start_projected.distance(transform(Point(nearest_point)))
        return jsonify({
            'point': nearest_point,
            'radius': round(radius, 2),
            'distance': passenger_route['distance']
        })
    except IndexError:
        return jsonify({})


@app.route('/directions', methods=['POST'])
def directions():
    """"""
    user_id = request.json.get('user_id')
    # To keep a fixed schema for the response, initialize these collections here
    handles = []
    prepared_routes = []
    # Profile, as it's called in the ORS, is the type of a vehicle, or a pedestrian, to route for
    profile = request.json.get('profile')
    if profile not in AVAILABLE_PROFILES:
        return f'Profile must be one of {AVAILABLE_PROFILES}', 400
    # Convert start, end and intermediate points from [lat, lon] to [lon, lat] format used in ORS & Shapely
    positions = [position[::-1] for position in request.json.get('positions')]
    # Start & end will mostly be manipulated via Shapely, so turn them into shapes
    start, finish = (Point(positions[i]) for i in (0, -1))
    # Reproject them to be used with Shapely (leave the spherical versions to save to the DB later)
    start_projected, finish_projected = (transform(point) for point in (start, finish))
    # Order intermediate positions along the route
    if len(positions) > 2:
        positions.sort(key=lambda x: start_projected.distance(transform(Point(x))))
    # Routing using existing routes
    from_route_id = request.json.get('from_route_id')  # UUID
    to_route_id = request.json.get('to_route_id')  # UUID
    from_route = to_shape(Route.query.get_or_404(from_route_id, ROUTE_NOT_FOUND_MESSAGE).route) if from_route_id else None
    to_route = to_shape(Route.query.get_or_404(to_route_id, ROUTE_NOT_FOUND_MESSAGE).route) if to_route_id else None
    if from_route and to_route:
        from_point, to_point = [point.coords[0] for point in nearest_points(from_route, to_route)]
        positions = [from_point, *positions, to_point]
    elif from_route:
        nearest_point = nearest_points(from_route, start)[0]
        positions.insert(0, nearest_point.coords[0])
    elif to_route:
        nearest_point = nearest_points(to_route, start)[0]
        positions.append(nearest_point.coords[0])
    # If routing via exisiting routes was request, only now is the position list final
    # On a driver's first request, several alternatives will be generated; let's call such a request 'initial'
    is_drivers_initial = profile == 'driving-car' and len(positions) == 2
    # Check if there are similar routes in the user's history; if there are any, return them along w/ the new ones
    if is_drivers_initial:
        # Get all the routes from the user's history
        past_routes = Route.query.filter(Route.trip_id != None, Route.user_id == user_id).all()
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
            tail = ors.directions([positions[0], nearest_to_start_4326], profile, alternatives=False)[0]
            head = ors.directions([nearest_to_finish_4326, positions[-1]], profile, alternatives=False)[0]
            if len(tail['geometry']) < 2:
                tail = empty_route
            if len(head['geometry']) < 2:
                head = empty_route
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
    if request.json.get('make_route', True):
        # If it's driver's 1st routing request, suggest alternatives
        routes = ors.directions(positions, profile, is_drivers_initial)
        # Save routes to DB
        all_routes = routes + prepared_routes
        route_ids = [uuid4() for _ in all_routes]
        for route, route_id in zip(all_routes, route_ids):
            db.session.add(Route(
                id=route_id,
                user_id=user_id,
                profile=profile,
                route=LineString(route['geometry']).wkt,
                start=start.wkt,
                finish=finish.wkt,
                distance=route['distance'],
                duration=route['duration']
            ))
        if profile == 'driving-car':
            # Get midpoints of the route's last segment for the user to drag on the screen
            routes_last_parts = routes if is_drivers_initial else ors.directions(positions[-2:], profile)
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
    else:
        route_id = uuid4()
        db.session.add(Route(
            id=route_id,
            user_id=user_id,
            profile=profile,
            start=start.wkt,
            finish=finish.wkt
        ))
        routes = FeatureCollection([Feature(id=route_id, geometry=LineString([start, finish]))])
    db.session.commit()
    return jsonify({
        'routes': routes,
        'handles': handles,
        'prepared_routes': prepared_routes,
    })


@app.route('/routes/<uuid:route_id>', methods=['GET'])
def get_route(route_id):
    route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    is_full = bool(route.route) and not request.args.get('full', 'true').lower() == 'false'
    route = to_shape(route.route) if is_full else LineString([
        to_shape(pt).coords[0] for pt in (route.start, route.finish)
    ])
    return {
        'route': Feature(geometry=route),
        'full': is_full
    }


@app.route('/routes/<uuid:route_id>', methods=['PUT'])
def delete_discarded_routes(route_id):
    user_id = request.args.get('user_id')
    trip_id = request.json.get('trip_id')
    try:
        count = Route.query.filter(Route.user_id == user_id, Route.id != route_id, Route.trip_id == None).delete()
        if count == 0:
            return 'User and route combination not found', 404
        Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).trip_id = trip_id
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return 'Such trip id already exists in the database', 400
    except Exception as e:
        db.session.rollback()
        return e, 400
    else:
        return ''


@app.route('/routes/<uuid:id_>/candidates', methods=['POST'])
def get_candidates(id_):
    target_route = Route.query.get_or_404(id_, ROUTE_NOT_FOUND_MESSAGE)
    try:
        candidate_route_ids = request.json['candidate_route_ids']
    except KeyError:
        return '"candidate_route_ids" missing from the request body', 400
    candidate_routes = Route.query.filter(
        Route.id.in_(candidate_route_ids),
        func.ST_Distance(Route.start, target_route.route) < 10000,
        func.ST_Distance(Route.finish, target_route.route) < 10000,
        func.ST_Distance(Route.finish, target_route.finish) < func.ST_Distance(Route.start, target_route.finish),
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
        func.ST_Distance(getattr(Route, candidate_attr), getattr(target_route, target_attr)) * weight
        for candidate_attr, target_attr, weight in sortings[target_route.profile]
    ]))
    return jsonify([route.id for route in candidate_routes])


@app.route('/geocode', methods=['GET'])
def geocode():
    text = request.args.get('text')
    result = ors.geocode(text)
    return jsonify(result) or '', 404


@app.route('/reverse', methods=['GET'])
def reverse_geocode():
    try:
        position = [float(coord) for coord in request.args.get('position', '').split(',')][0: 2]
        return ors.reverse_geocode(position) or '', 404
    except ValueError:
        return '', 400


@app.route('/suggest', methods=['GET'])
def suggest():
    text = request.args.get('text')
    result = ors.suggest(text)
    return jsonify(FeatureCollection([
        Feature(
            geometry=feature['geometry'],
            properties=feature['properties']
        ) for feature in result]
    )) if result else '', 404
