from flask import Flask, request
from flask.json import jsonify
from openrouteservice.convert import decode_polyline

import ors
import postgis
from helpers import parse_position


app = Flask(__name__)


@app.route('/', methods=['GET'])
def healthcheck():
    return jsonify({'status': 'OK'})


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


@app.route('/directions/', methods=['GET'])
def directions():
    start = parse_position(request.args.get('start'))
    end = parse_position(request.args.get('end'))
    profile = request.args.get('profile')
    routes = ors.directions(start, end, profile)
    geoms = [decode_polyline(route['geometry']) for route in routes]
    features = [{'type': 'Feature', 'geometry': geom} for geom in geoms]
    return jsonify({'type': 'FeatureCollection', 'features': features})


@app.route('/snap/', methods=['GET'])
def snap_to_road():
    position = parse_position(request.args.get('position'))
    snapped = postgis.snap_to_road(position)
    lon, lat = json.loads(snapped)['coordinates']
    return f'{lon},{lat}'


if __name__ == '__main__':
    app.run()
