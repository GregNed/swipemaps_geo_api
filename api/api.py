import json

from flask import Flask, request, jsonify
from openrouteservice.convert import decode_polyline

from api import ors
from api import postgis
from api.helpers import parse_position


app = Flask(__name__)


@app.route('/', methods=['GET'])
def healthcheck():
    return jsonify({'status': 'OK'})


@app.route('/directions/', methods=['GET'])
def directions():
    profile = request.args.get('profile')
    positions = request.args.get('positions')
    positions_parsed = [parse_position(p) for p in positions.split(';')]
    routes = ors.directions(positions_parsed, profile)
    geoms = [decode_polyline(route['geometry']) for route in routes]
    features = [{'type': 'Feature', 'geometry': geom} for geom in geoms]
    return jsonify({'type': 'FeatureCollection', 'features': features})


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


@app.route('/snap/', methods=['GET'])
def snap_to_road():
    position = parse_position(request.args.get('position'))
    snapped = postgis.snap_to_road(position)
    lon, lat = json.loads(snapped)['coordinates']
    return f'{lon},{lat}'


if __name__ == '__main__':
    app.run()
