from geojson import Point, LineString, Feature, FeatureCollection
from flask import Flask, request, jsonify
from openrouteservice.convert import decode_polyline

from . import ors
from .geom_ops import get_midpoint
from .postgis import snap_to_road
from .helpers import parse_position


app = Flask(__name__)


@app.route('/', methods=['GET'])
def healthcheck():
    return jsonify({'status': 'OK'})


@app.route('/snap/', methods=['GET'])
def snap():
    positions = request.args.get('positions')
    positions_parsed = [parse_position(p) for p in positions.split(';')]
    positions_snapped = [snap_to_road(p) for p in positions_parsed]
    return jsonify(FeatureCollection([Feature(i, Point(p)) for i, p in enumerate(positions_snapped)]))


@ app.route('/directions/', methods=['GET'])
def directions():
    profile = request.args.get('profile')
    positions = request.args.get('positions')
    positions_parsed = [parse_position(p) for p in positions.split(';')]  # use GeoJSON utils.map?
    routes = ors.directions(positions_parsed, profile)
    route_coords = [decode_polyline(route['geometry'])['coordinates'] for route in routes]
    sec_to_last_indexes = [coords.index(list(map(lambda x: round(x, 5), positions_parsed[-2]))) for coords in route_coords]
    route_last_part_coords = [coords[i:] for coords, i in zip(route_coords, sec_to_last_indexes)]
    handles = [get_midpoint(coords) for coords in route_last_part_coords]
    return jsonify({
        'routes': FeatureCollection([Feature(i, LineString(coords)) for i, coords in enumerate(route_coords)]),
        'handles': FeatureCollection([Feature(i, Point(handle)) for i, handle in enumerate(handles)]),
    })


@ app.route('/geocode/', methods=['GET'])
def geocode():
    text = request.args.get('text')
    result = ors.geocode(text)
    return jsonify(result)


@ app.route('/reverse/', methods=['GET'])
def reverse_geocode():
    position = parse_position(request.args.get('point'))
    result = ors.reverse_geocode(position)
    return jsonify(result)


if __name__ == '__main__':
    app.run()
