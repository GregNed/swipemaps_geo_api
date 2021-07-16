import json
from typing import Callable
from uuid import uuid4

import pyproj
from shapely.geometry import Point, LineString, MultiLineString, mapping
from shapely.ops import nearest_points, substring, snap, linemerge, unary_union, split
from geojson import Feature, FeatureCollection
from flask import request, jsonify, abort, Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from geoalchemy2.shape import to_shape

from api import app, db, ors
from api.models import Route


AVAILABLE_PROFILES = ('driving-car', 'foot-walking')
POINT_PROXIMITY_THRESHOLD = 1000
TRANSFORM = pyproj.Transformer.from_crs(4326, 3857, always_xy=True)


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
        abort(Response(f'Profile must be one of {AVAILABLE_PROFILES}', 400))
    # Convert start, end and intermediate points from [lat, lon] to [lon, lat] format used in ORS & Shapely
    positions = [position[::-1] for position in request.json.get('positions')]
    # Start & end will mostly be manipulated via Shapely, so turn them into shapes
    start = Point(positions[0])
    finish = Point(positions[-1])
    # Routing using existing routes
    from_route_id = request.json.get('from_route_id')  # UUID
    to_route_id = request.json.get('to_route_id')  # UUID
    from_route = to_shape(Route.query.get_or_404(from_route_id).route) if from_route_id else None
    to_route = to_shape(Route.query.get_or_404(to_route_id).route) if to_route_id else None
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
        # Reproject start & finish to Web Mercator to use them with Shapely
        start_3857, finish_3857 = [transform(Point(positions[i])) for i in (0, -1)]
        # Get all the routes from the user's history
        past_routes = Route.query.filter(Route.trip_id != None, Route.user_id == user_id).all()
        # Filter out those whose start & finish were close enough to the currently requested ones
        similar_routes = [
            {'geometry': to_shape(route.route), 'distance': route.distance, 'duration': route.duration}
            for route in past_routes
            if transform(to_shape(route.start)).distance(start_3857) < POINT_PROXIMITY_THRESHOLD
            and transform(to_shape(route.finish)).distance(finish_3857) < POINT_PROXIMITY_THRESHOLD
        ]
        for index, route in enumerate(similar_routes):
            route_geom = transform(LineString(route['geometry']))
            # Get the closest points on the past route to counterparts requested by the user
            nearest_to_start, _ = nearest_points(route_geom, start_3857)
            nearest_to_finish, _ = nearest_points(route_geom, finish_3857)
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
                tail_snapped = LineString([snap(Point(v), nearest_points(common_part, Point(v))[0], 25) for v in tail_geom.coords])
                if tail_snapped.overlaps(common_part):
                    tail_geom, common_part = tail_snapped.symmetric_difference(common_part)
                elif tail_snapped.within(common_part):
                    tail_geom = LineString()
            if head['geometry']:
                head_snapped = LineString([snap(Point(v), nearest_points(common_part, Point(v))[0], 25) for v in head_geom.coords])
                if head_snapped.overlaps(common_part):
                    head_geom, common_part = head_snapped.symmetric_difference(common_part)
                elif head_snapped.within(common_part):
                    head_geom = LineString()
            # Stitch them together
            parts_to_merge = list(filter(bool, (tail_geom, common_part, head_geom)))
            full_route = linemerge(unary_union(parts_to_merge)) if len(parts_to_merge) > 1 else common_part
            prepared_routes.append(Feature(
                id=index,
                geometry=transform(full_route, to_wgs84=True),
                properties={
                    attr: sum([part[attr] for part in (route, tail, head)])  # sum distance & duration of the parts
                    for attr in ('distance', 'duration')
                }
            ))
    # User may opt to drive ad-hoc instead of preparing a route; if make_route is False, only the endpoint will be saved
    if request.json.get('make_route', True):
        # If it's driver's 1st routing request, suggest alternatives
        routes = ors.directions(positions, profile, is_drivers_initial)
        # Save routes to DB
        route_ids = [uuid4() for _ in routes]
        for route, route_id in zip(routes, route_ids):
            db.session.add(Route(
                id=route_id,
                user_id=user_id,
                # change to accept WKT/WKB
                route=json.dumps(mapping(LineString(route['geometry']))),
                start=json.dumps(mapping(start)),
                finish=json.dumps(mapping(finish)),
                distance=route['distance'],
                duration=route['duration']
            ))
        # Get midpoints of the route's last segment for the user to drag on the screen
        if profile == 'driving-car':
            routes_last_parts = routes if is_drivers_initial else ors.directions(positions[-2:], profile)
            routes_last_parts = [route['geometry'] for route in routes_last_parts]
            handles = [LineString(route).interpolate(0.5, normalized=True) for route in routes_last_parts]
            handles = [Point(handle.coords[0]) for handle in handles]
            handles = FeatureCollection([Feature(route_id, handle) for route_id, handle in zip(route_ids, handles)])
        # Prepare the response
        routes = FeatureCollection([
            Feature(
                id=route_id,
                geometry=LineString(route['geometry']),
                properties={attr: route[attr] for attr in ('distance', 'duration')}
            ) for route_id, route in zip(route_ids, routes)])
    else:
        route_id = uuid4()
        db.session.add(Route(
            id=route_id,
            user_id=user_id,
            start=json.dumps(mapping(start)),
            finish=json.dumps(mapping(finish))
        ))
        routes = FeatureCollection([Feature(id=route_id, geometry=LineString([start, finish]))])
    db.session.commit()
    return jsonify({
        'routes': routes,
        'handles': handles,
        'prepared_routes': FeatureCollection(prepared_routes),
    })


@app.route('/routes/<uuid:route_id>', methods=['GET'])
def get_route(route_id):
    route = Route.query.get_or_404(route_id)
    is_full = route.route and not request.args.get('full', 'true').lower() == 'false'
    route = to_shape(route.route) if is_full else LineString([to_shape(pt).coords[0] for pt in (route.start, route.finish)])
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
            abort(Response('User and route combination not found', 404))
        Route.query.get_or_404(route_id).trip_id = trip_id
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return Response('Such trip id already exists in the database', 400)
    except Exception as e:
        db.session.rollback()
        return Response(e, 400)
    else:
        return ''


@app.route('/candidates', methods=['GET'])
def get_candidates():
    route_id = request.args.get('route_id')
    candidate_route_ids = request.args.get('candidate_route_ids').split(',')
    route = Route.query.get_or_404(route_id)
    candidate_routes_sorted = Route.query.filter(Route.trip_id != None, Route.id.in_(candidate_route_ids)).order_by(func.ST_Distance(Route.start, route.start))
    candidate_ids = [route.id for route in candidate_routes_sorted]
    return jsonify(candidate_ids)


@app.route('/geocode', methods=['GET'])
def geocode():
    text = request.args.get('text')
    result = ors.geocode(text)
    return jsonify(result) or abort(404)


@app.route('/reverse', methods=['GET'])
def reverse_geocode():
    try:
        position = [float(coord) for coord in request.args.get('position', '').split(',')][0: 2]
        return ors.reverse_geocode(position) or abort(404)
    except ValueError:
        abort(400)


@app.route('/suggest', methods=['GET'])
def suggest():
    text = request.args.get('text')
    result = ors.suggest(text)
    return jsonify(FeatureCollection([
        Feature(
            geometry=feature['geometry'],
            properties=feature['properties']
        ) for feature in result]
    )) if result else abort(404)
