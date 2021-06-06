import random
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

from geojson import Point, LineString, Feature, FeatureCollection
from flask import request, jsonify, abort, Response
from sqlalchemy import func

from api import app, db, ors
from api.models import Start, Finish, Route
from api.geom_ops import get_midpoint
from api.postgis import snap_to_road
from api.helpers import parse_positions


@app.route('/', methods=['GET'])
def healthcheck():
    return jsonify({'status': 'OK'})


@app.route('/snap/', methods=['GET'])
def snap():
    positions = parse_positions(request.args.get('positions'))
    with ThreadPoolExecutor() as executor:
        snapped = executor.map(snap_to_road, positions)
    return jsonify(FeatureCollection([Feature(i, Point(p)) for i, p in enumerate(snapped, 1)]))


@app.route('/directions/', methods=['GET'])
def directions():
    # Parse query string params
    profile = request.args.get('profile')
    user_id = request.args.get('user_id')
    positions = parse_positions(request.args.get('positions'))
    # Save start & finish points to DB
    start = Start(
        geom=str(Point(positions[0])),
        user_id=user_id
    )
    finish = Finish(
        geom=str(Point(positions[-1])),
        user_id=user_id
    )
    db.session().add(start)
    db.session().add(finish)
    db.session.commit()
    # If it's 1st routing request for user's session, - request alternatives
    is_initial = len(positions) == 2
    routes = ors.directions(positions, profile, is_initial)
    # Save routes to DB
    for route in routes:
        route = Route(
            geom=str(LineString(route)),
            user_id=user_id
        )
        db.session.add(route)
    db.session.commit()
    # Get handles
    routes_last_parts = routes if is_initial else ors.directions(positions[-2:], profile)
    handles = [get_midpoint(route) for route in routes_last_parts]
    return jsonify({
        'user_id': user_id,
        'routes': FeatureCollection([Feature(i, LineString(coords)) for i, coords in enumerate(routes, 1)]),
        'handles': FeatureCollection([Feature(i, Point(handle)) for i, handle in enumerate(handles, 1)])
    })


@app.route('/users/<uuid:user_id>/routes/<int:route_id>', methods=['DELETE'])
def delete_discarded_routes(user_id, route_id):
    count_deleted = Route.query.filter(Route.user_id == user_id, Route.id != route_id).delete()
    if count_deleted:
        db.session.commit()
        return str(user_id)
    else:
        abort(Response('The requested user and route combination was not found', 404))


@app.route('/sortPassengers', methods=['GET'])
def sort_passengers(user_id, route_id):
    user_id = request.args.get('user_id')
    route_id = request.args.get('route_id')
    user_start = Location.query.filter(Location.user_id == user_id, Location.kind == 'start').first_or_404()
    user_finish = Location.query.filter(Location.user_id == user_id, Location.kind == 'finish').first_or_404()
    candidates = Location.query.order_by('user_id')
    return jsonify([{
        'user_id': user_id,
        'route_id': route_id,
        'passengers': {
            'id': uuid4(),
        }} for _ in range(2, random.randint(3, 10))])


@app.route('/geocode/', methods=['GET'])
def geocode():
    text = request.args.get('text')
    result = ors.geocode(text)
    return jsonify(result)


@app.route('/reverse/', methods=['GET'])
def reverse_geocode():
    position = parse_positions(request.args.get('position'))[0]
    return jsonify(ors.reverse_geocode(position))
