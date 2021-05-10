import json

from flask import Flask, request
from openrouteservice.convert import decode_polyline

import api_calls
import db_calls
from helpers import parse_coords


app = Flask(__name__)


@app.route('/', methods=['GET'])
def healthcheck():
    return json.dumps({'status': 'OK'})


@app.route('/geocode/', methods=['GET'])
def geocode():
    text = request.args.get('text')
    result = api_calls.geocode(text)
    return json.dumps(result)


@app.route('/reverse/', methods=['GET'])
def reverse_geocode():
    position = parse_coords(request.args.get('point'))
    result = api_calls.reverse_geocode(position)
    return json.dumps(result)


@app.route('/directions/', methods=['GET'])
def directions():
    start = parse_coords(request.args.get('start'))
    end = parse_coords(request.args.get('end'))
    profile = request.args.get('profile')
    routes = api_calls.directions(start, end, profile)
    geoms = [decode_polyline(route['geometry']) for route in routes]
    features = [{'type': 'Feature', 'geometry': geom} for geom in geoms]
    return json.dumps({'type': 'FeatureCollection', 'features': features})


@app.route('/snap/', methods=['GET'])
def snap_to_road():
    position = parse_coords(request.args.get('position'))
    snapped = db_calls.snap_to_road(position)
    lon, lat = json.loads(snapped)['coordinates']
    return f'{lon},{lat}'


if __name__ == '__main__':
    app.run()
