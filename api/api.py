from concurrent.futures import ThreadPoolExecutor

from geojson import Point, LineString, Feature, FeatureCollection
from flask import Flask, request, jsonify

from . import ors
from .geom_ops import get_midpoint
from .postgis import snap_to_road
from .helpers import parse_positions


app = Flask(__name__)


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
    profile = request.args.get('profile')
    positions = parse_positions(request.args.get('positions'))
    alternatives = len(positions) == 2
    routes = ors.directions(positions, profile, alternatives)
    routes_last_parts = routes if alternatives else ors.directions(positions[-2:], profile)
    handles = [get_midpoint(route) for route in routes_last_parts]
    return jsonify({
        'routes': FeatureCollection([Feature(i, LineString(coords)) for i, coords in enumerate(routes, 1)]),
        'handles': FeatureCollection([Feature(i, Point(handle)) for i, handle in enumerate(handles, 1)])
    })


@app.route('/geocode/', methods=['GET'])
def geocode():
    text = request.args.get('text')
    result = ors.geocode(text)
    return jsonify(result)


@app.route('/reverse/', methods=['GET'])
def reverse_geocode():
    position = parse_positions(request.args.get('position'))[0]
    return jsonify(ors.reverse_geocode(position))


if __name__ == '__main__':
    app.run()
