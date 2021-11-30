import os
from typing import Iterable

import requests
import openrouteservice as ors
from flask import abort

from . import app


# Connection constants
ORS_ENDPOINT = os.getenv('ORS_ENDPOINT')
ORS_API_KEY = os.getenv('ORS_API_KEY', '')
PELIAS_ENDPOINT = os.getenv('PELIAS_ENDPOINT')
PELIAS_API_KEY = os.getenv('PELIAS_API_KEY', '')
SUPPORTED_REGIONS = 'Moscow City', 'Moscow Oblast', 'Irkutsk', 'Mari El'


def directions(
    positions: list[list[float]],
    profile: str,
    alternatives: bool = False,
    geometry: bool = True
) -> list[dict]:
    """"""
    client = ors.Client(base_url=ORS_ENDPOINT, key=ORS_API_KEY)
    args = {
        'profile': profile,
        'instructions': False,
        'geometry': geometry,
        'format': 'geojson' if geometry else 'json',
        'alternative_routes': {
            'target_count': app.config['ORS_MAX_ALTERNATIVES'],
            'weight_factor': 1.4,
            'share_factor': 0.8
        } if alternatives else False
    }
    try:
        res = client.directions(positions, **args)
    except Exception as e:
        abort(500, str(e))
    try:
        routes = [{
            'geometry': route['geometry']['coordinates'],
            'distance': route['properties']['summary']['distance'],
            'duration': route['properties']['summary']['duration']
        } for route in res['features']]
    except KeyError:
        routes = [{
            'geometry': positions,
            'distance': 0.0,
            'duration': 0.0
        } for route in res['features']]
    return routes or abort(500, 'ORS failed to route between the requested locations')


def geocode(text, focus, max_occurrences=1):
    """"""
    focus_lat, focus_lon = focus
    params = {
        'text': text,
        'layers': 'address,venue,locality',
        'size': max_occurrences,
        'sources': 'openstreetmap',
        'focus.point.lon': focus_lon,
        'focus.point.lat': focus_lat,
        'boundary.country': 'RU',
        'lang': 'ru',
        'api_key': PELIAS_API_KEY
    }
    res = requests.get(PELIAS_ENDPOINT + '/search', params=params)
    res.raise_for_status()
    feature = res.json()['features'][0]
    feature['properties'] = {
        'address': feature['properties']['name'],
        'locality': feature['properties'].get('locality') or feature['properties'].get('region')
    }
    return feature


def suggest(text, focus):
    """"""
    focus_lat, focus_lon = focus
    params = {
        'text': text,
        'layers': 'address,venue,locality',
        'sources': 'openstreetmap',
        'focus.point.lon': focus_lon,
        'focus.point.lat': focus_lat,
        'boundary.country': 'RU',
        'api_key': PELIAS_API_KEY
    }
    res = requests.get(PELIAS_ENDPOINT + '/autocomplete', params=params)
    res.raise_for_status()
    results = filter(
        lambda i: i['properties']['region'] in SUPPORTED_REGIONS,
        res.json()['features']
    )
    return [{
        'id': feature['properties']['id'].split('/')[1],
        'geometry': feature['geometry'],
        'properties': {
            'address': feature['properties']['name'],
            'locality': feature['properties'].get('locality') or feature['properties'].get('region')
        }
    } for feature in results]

def reverse_geocode(location: Iterable, focus: Iterable):
    """"""
    params = {
        'point.lon': location[0],
        'point.lat': location[1],
        'layers': 'address,venue',
        'sources': 'openstreetmap',
        'size': 1,
        'focus.point.lon': focus[0],
        'focus.point.lat': focus[1],
        'boundary.country': 'RU',
        'lang': 'ru',
        'api_key': PELIAS_API_KEY
    }
    res = requests.get(PELIAS_ENDPOINT + '/reverse', params=params)
    res.raise_for_status()
    feature = res.json()['features'][0]
    feature['id'] = int(feature['properties']['id'].split('/')[1])
    feature['properties'] = {
        'address': feature['properties']['name'],
        'locality': feature['properties'].get('locality') or feature['properties'].get('region')
    }
    return feature
