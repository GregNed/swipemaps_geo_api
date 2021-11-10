import os

import requests
import openrouteservice as ors
from flask import abort

from . import app


# Connection constants
ORS_ENDPOINT = os.getenv('ORS_ENDPOINT')
PELIAS_ENDPOINT = os.getenv('PELIAS_ENDPOINT')
SUPPORTED_REGIONS = 'Moscow City', 'Moscow Oblast', 'Irkutsk', 'Mari El'
MOSCOW_CENTER = [55.754801, 37.622311]


def directions(
    positions: list[list[float]],
    profile: str,
    alternatives: bool = False,
    geometry: bool = True
) -> list[dict]:
    """"""
    client = ors.Client(base_url=ORS_ENDPOINT)
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


def geocode(text, focus=MOSCOW_CENTER, max_occurrences=1):
    """"""
    focus_lat, focus_lon = focus
    params = {
        'text': text,
        'layers': 'address,venue,street,locality',
        'size': max_occurrences,
        'sources': 'openstreetmap',
        'focus.point.lon': focus_lon,
        'focus.point.lat': focus_lat,
        'boundary.country': 'RU',
        'lang': 'ru',
    }
    res = requests.get(PELIAS_ENDPOINT + '/search', params=params)
    res.raise_for_status()
    feature = res.json()['features'][0]
    feature['properties'] = {
        'address': feature['properties']['name'],
        'locality': feature['properties']['locality']
    }
    return feature


def reverse_geocode(location, focus=MOSCOW_CENTER, max_occurrences=1):
    """"""
    lat, lon = location
    focus_lat, focus_lon = focus
    params = {
        'point.lon': lon,
        'point.lat': lat,
        'layers': 'address,venue',
        'sources': 'openstreetmap',
        'size': max_occurrences,
        'focus.point.lon': focus_lon,
        'focus.point.lat': focus_lat,
        'boundary.country': 'RU',
        'lang': 'ru',
    }
    res = requests.get(PELIAS_ENDPOINT + '/reverse', params=params)
    res.raise_for_status()
    feature = res.json()['features'][0]
    feature['id'] = int(feature['properties']['id'].split('/')[1])
    feature['properties'] = {
        'address': feature['properties']['name'],
        'locality': feature['properties']['locality']
    }
    return feature


def suggest(text, focus=MOSCOW_CENTER):
    """"""
    focus_lat, focus_lon = focus
    params = {
        'text': text,
        'layers': 'address,venue,street,locality',
        'sources': 'openstreetmap',
        'focus.point.lon': focus_lon,
        'focus.point.lat': focus_lat,
        'boundary.country': 'RU',
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
            'locality': feature['properties']['locality']
        }
    } for feature in results]
