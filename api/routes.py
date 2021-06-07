from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import requests

from geojson import Point, LineString, Feature, FeatureCollection
from flask import request, jsonify, abort, Response
from sqlalchemy import func

from api import app, db, ors
from api.models import Route
from api.geom_ops import get_midpoint
from api.postgis import snap_to_road
from api.helpers import parse_positions


@app.route('/', methods=['GET'])
def healthcheck():
    return jsonify({'status': 'OK'})


@app.route('/snap/', methods=['GET'])
def snap():
    positions = parse_positions(request.json.get('positions'))
    with ThreadPoolExecutor() as executor:
        snapped = executor.map(snap_to_road, positions)
    return jsonify(FeatureCollection([Feature(i, Point(p)) for i, p in enumerate(snapped, 1)]))


@app.route('/directions/', methods=['POST'])
def directions():
    # Parse query string params
    profile = request.json.get('profile')
    user_id = request.json.get('user_id')
    positions = parse_positions(request.json.get('positions'))
    # If it's driver's 1st routing request, do with alternatives
    is_initial = (profile == 'driving-car') and (len(positions) == 2)
    routes = ors.directions(positions, profile, is_initial)
    # Save routes to DB
    route_ids = [uuid4() for route in routes]
    for index, route in enumerate(routes):
        db.session.add(Route(
            id=route_ids[index],
            user_id=user_id,
            route=str(LineString(route)),
            start=str(Point(positions[0])),
            finish=str(Point(positions[-1]))
        ))
    db.session.commit()
    # Get handles
    routes_last_parts = routes if is_initial else ors.directions(positions[-2:], profile)
    handles = [get_midpoint(route) for route in routes_last_parts]
    return jsonify({
        'user_id': user_id,
        'routes': FeatureCollection([Feature(i, LineString(route)) for i, route in zip(route_ids, routes)]),
        'handles': FeatureCollection([Feature(i, Point(handle)) for i, handle in zip(route_ids, handles)])
    })


@app.route('/routes/<uuid:route_id>', methods=['PUT'])
def delete_discarded_routes(route_id):
    user_id = request.args.get('user_id')
    trip_id = request.json.get('trip_id')
    count_deleted = Route.query.filter(
        Route.user_id == user_id,
        Route.id != route_id,
        Route.trip_id == None
    ).delete()
    db.session.commit()
    if count_deleted == 0:
        abort(Response('User and route combination not found', 404))
    Route.query.get(route_id).trip_id = trip_id
    db.session.commit()
    return ''


@app.route('/candidates', methods=['GET'])
def get_candidates():
    user_id = request.args.get('user_id')
    route_id = request.args.get('route_id')
    route = Route.query.get_or_404(route_id)
    if route.route:
        candidates = Route.query.filter(Route.route == None)
    else:
        candidates = Route.query.filter(Route.route != None)
    # candidates.order_by(func.ST_DWithin())
    # return jsonify([{
    #     'user_id': user_id,
    #     'route_id': route_id,
    #     'passengers': {
    #         'id': uuid4(),
    #     }} for _ in range(2, random.randint(3, 10))])


@app.route('/geocode/', methods=['GET'])
def geocode():
    text = request.args.get('text')
    result = ors.geocode(text)
    return jsonify(result)


@app.route('/reverse/', methods=['GET'])
def reverse_geocode():
    position = parse_positions(request.args.get('position'))[0]
    return jsonify(ors.reverse_geocode(position))
