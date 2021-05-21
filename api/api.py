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


@app.route('/directions/', methods=['GET'])
def directions():
    profile = request.args.get('profile')
    positions = request.args.get('positions')
    positions_parsed = [parse_position(p) for p in positions.split(';')]
    positions_snapped = [snap_to_road(p) for p in positions_parsed]
    routes = ors.directions(positions_snapped, profile)
    geoms = [decode_polyline(route['geometry']) for route in routes]
    midpoints = [get_midpoint(geom) for geom in geoms]
    routes_fc = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': geom} for geom in geoms]}
    midpoints_fc = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': midpoint}} for midpoint in midpoints]}
    return jsonify({'routes': routes_fc, 'midpoints': midpoints_fc})


@app.route('/geocode/', methods=['GET'])
def geocode():
    text = request.args.get('text')
    result = ors.geocode(text)
    return jsonify(result)


@app.route('/reverse/', methods=['GET'])
def reverse_geocode():
    position = parse_position(request.args.get('point'))
    result = ors.reverse_geocode(position)
    return jsonify(result)


if __name__ == '__main__':
    app.run()
