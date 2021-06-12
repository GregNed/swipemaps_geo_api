from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import shapely.geometry
from shapely.ops import nearest_points
from geojson import Point, LineString, Feature, FeatureCollection
from flask import request, jsonify, abort, Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from geoalchemy2.shape import to_shape

from api import app, db, ors
from api.models import Route
from api.postgis import snap_to_road
from api.helpers import parse_positions


@app.route('/', methods=['GET'])
def healthcheck():
    return jsonify({'status': 'OK'})


@app.route('/directions/', methods=['POST'])
def directions():
    # Parse the request
    available_profiles = ('driving-car', 'foot-walking')
    profile = request.json.get('profile')
    if profile not in available_profiles:
        abort(Response(f'Profile must be one of {available_profiles}', 400))
    positions = parse_positions(request.json.get('positions'))
    from_route_id = request.json.get('from_route_id')
    to_route_id = request.json.get('to_route_id')
    if from_route_id and to_route_id:
        from_point, to_point = nearest_points(
            to_shape(Route.query.get_or_404(from_route_id).route),
            to_shape(Route.query.get_or_404(to_route_id).route)
        )
        positions.insert(0, from_point.coords[0])
        positions.append(to_point.coords[0])
    if from_route_id:
        route = Route.query.get_or_404(from_route_id)
        nearest_point = nearest_points(to_shape(route.route), shapely.geometry.Point(positions[0]))[0]
        positions.insert(0, nearest_point.coords[0])
    if to_route_id:
        route = Route.query.get_or_404(to_route_id)
        nearest_point = nearest_points(to_shape(route.route), shapely.geometry.Point(positions[0]))[0]
        positions.append(nearest_point.coords[0])
    start = Point(positions[0])
    finish = Point(positions[-1])
    user_id = request.json.get('user_id')
    make_route = request.json.get('make_route', True)
    handles = []
    if make_route:
        # If it's driver's 1st routing request, do with alternatives
        is_initial = (profile == 'driving-car' and len(positions) == 2)
        routes = ors.directions(positions, profile, is_initial)
        # Save routes to DB
        route_ids = [uuid4() for route in routes]
        for route, route_id in zip(routes, route_ids):
            db.session.add(Route(
                id=route_id,
                user_id=user_id,
                route=str(LineString(route['geometry'])),
                start=str(start),
                finish=str(finish),
                distance=route['distance'],
                duration=route['duration']
            ))
        # Get midpoints of the route's last segment for the user to drag on the screen
        if profile == 'driving-car':
            routes_last_parts = routes if is_initial else ors.directions(positions[-2:], profile)
            routes_last_parts = [route['geometry'] for route in routes_last_parts]
            handles = [shapely.geometry.LineString(route).interpolate(0.5, normalized=True) for route in routes_last_parts]
            handles = [Point(handle.coords[0]) for handle in handles]
            handles = FeatureCollection([Feature(route_id, handle) for route_id, handle in zip(route_ids, handles)])
        # Prepare the response
        routes = FeatureCollection([
            Feature(
                id=route_id,
                geometry=LineString(route['geometry']),
                properties={
                    'distance': route['distance'],
                    'duration': route['duration']
                })
            for route_id, route in zip(route_ids, routes)])
    else:
        route_id = uuid4()
        db.session.add(Route(id=route_id, user_id=user_id, start=str(start), finish=str(finish)))
        routes = FeatureCollection([Feature(id=route_id, geometry=LineString([start, finish]))])
    db.session.commit()
    return jsonify({'routes': routes, 'handles': handles})


@app.route('/routes/<uuid:route_id>', methods=['GET'])
def get_route(route_id):
    route = Route.query.get_or_404(route_id)
    if not route.route or request.args.get('full', 'true').lower() == 'false':
        return {
            'route': Feature(geometry=LineString([
                to_shape(route.start).coords[0],
                to_shape(route.finish).coords[0],
            ])),
            'full': False
        }
    else:
        return {
            'route': Feature(geometry=to_shape(route.route)),
            'full': True
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


@app.route('/geocode/', methods=['GET'])
def geocode():
    text = request.args.get('text')
    result = ors.geocode(text)
    return jsonify(result)


@app.route('/reverse/', methods=['GET'])
def reverse_geocode():
    position = parse_positions(request.args.get('position'))[0]
    return jsonify(ors.reverse_geocode(position))


@app.route('/snap/', methods=['GET'])
def snap():
    positions = parse_positions(request.json.get('positions'))
    with ThreadPoolExecutor() as executor:
        snapped = executor.map(snap_to_road, positions)
    return jsonify(FeatureCollection([Feature(i, Point(p)) for i, p in enumerate(snapped, 1)]))
