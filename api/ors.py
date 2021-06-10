import requests
import openrouteservice as ors


API_KEY = '5b3ce3597851110001cf6248ec409dc3a99a42bc8a80b2f87c0da955'
ORS_ENDPOINT = 'http://ors:8080/ors'
# ORS_ENDPOINT = 'http://ors-test:8080/ors'
# PELIAS_ENDPOINT = 'http://localhost:4000/v1'
PELIAS_ENDPOINT = 'https://api.openrouteservice.org/geocode'
MOSCOW_CENTER = {
    'focus.point.lon': 37.622311,
    'focus.point.lat': 55.754801
}
MMO_BBOX = {
    "boundary.rect.min_lon": 35.1484940,
    "boundary.rect.min_lat": 54.2556960,
    "boundary.rect.max_lon": 40.2056880,
    "boundary.rect.max_lat": 56.9585110
}


def directions(positions, profile, alternatives=False):
    """"""
    client = ors.Client(base_url=ORS_ENDPOINT)
    args = {
        'instructions': False,
        'profile': profile,
    }
    if alternatives:
        args |= {
            'alternative_routes': {
                'target_count': 3,
                'weight_factor': 2.0,
                'share_factor': 0.8
            }
        }
    try:
        res = client.directions(positions, **args)
        return [{
            'geometry': ors.convert.decode_polyline(route['geometry'])['coordinates'],
            'distance': route['summary']['distance'],
            'duration': route['summary']['duration']
        } for route in res.get('routes', [])]
    except ors.exceptions.ApiError:
        return []


def geocode(text, focus=MOSCOW_CENTER, bbox=MMO_BBOX, max_occurrences=5):
    """"""
    params = {
        'api_key': API_KEY,
        'text': text,
        'layers': 'address,venue',
        'size': max_occurrences,
        'boundary.country': 'RU',
        'sources': 'openstreetmap'
    } | MOSCOW_CENTER | MMO_BBOX
    res = requests.get(
        PELIAS_ENDPOINT + '/search',
        params=params
    )
    res.raise_for_status()
    return res.json()


def reverse_geocode(location, max_occurrences=5):
    """"""
    lon, lat = location
    params = {
        'api_key': API_KEY,
        'point.lon': lon,
        'point.lat': lat,
        'layers': 'address',
        'size': max_occurrences,
        'boundary.country': 'RU',
        'sources': 'openstreetmap'
    } | MOSCOW_CENTER | MMO_BBOX
    res = requests.get(
        PELIAS_ENDPOINT + '/reverse',
        params=params
    )
    res.raise_for_status()
    return res.json()


def suggest(location, max_occurrences=5):
    """"""
    lon, lat = location
    params = {
        'api_key': API_KEY,
        'point.lon': lon,
        'point.lat': lat,
        'layers': 'address, venue',
        'boundary.country': 'RU',
        'sources': 'openstreetmap'
    } | MOSCOW_CENTER | MMO_BBOX
    res = requests.get(
        PELIAS_ENDPOINT + '/autocomplete',
        params=params
    )
    res.raise_for_status()
    return res.json()
