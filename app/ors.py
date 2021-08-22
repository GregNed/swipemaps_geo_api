import os
import requests
import openrouteservice as ors


# Connection constants
API_KEY = os.getenv('ORS_API_KEY')
ORS_ENDPOINT = os.getenv('ORS_ENDPOINT')
PELIAS_ENDPOINT = os.getenv('PELIAS_ENDPOINT')
# The app is scoped to Moscow and the Moscow Region for now, so tune the service to focus on that area
MOSCOW_CENTER = [55.754801, 37.622311]
MMO_BBOX = [[54.2556960, 35.1484940], [56.9585110, 40.2056880]]


def directions(positions: list[float], profile: str, alternatives: bool = False, geometry: bool = True) -> list[dict]:
    """"""
    client = ors.Client(base_url=ORS_ENDPOINT)
    args = {
        'profile': profile,
        'instructions': False,
        'geometry': geometry,
        'format': 'geojson' if geometry else 'json',
        'alternative_routes': {
            'target_count': 3,
            'weight_factor': 2.0,
            'share_factor': 0.8
        } if alternatives else False
    }
    res = client.directions(positions, **args)
    return [{
        'geometry': route['geometry']['coordinates'] if geometry else {},
        # Distance & duration are missing for single-segment routes apparently
        'distance': route['properties']['summary']['distance'],
        'duration': route['properties']['summary']['duration']
    } for route in res['features']]


def geocode(text, focus=MOSCOW_CENTER, bbox=MMO_BBOX, max_occurrences=1):
    """"""
    try:
        focus_lat, focus_lon = focus
        nw, se = bbox
        params = {
            'api_key': API_KEY,
            'text': text,
            'layers': 'address,venue',
            'size': max_occurrences,
            'sources': 'openstreetmap',
            'focus.point.lon': focus_lon,
            'focus.point.lat': focus_lat,
            'boundary.country': 'RU',
            'boundary.rect.min_lon': nw[1],
            'boundary.rect.min_lat': nw[0],
            'boundary.rect.max_lon': se[1],
            'boundary.rect.max_lat': se[0]

        }
        res = requests.get(f'{PELIAS_ENDPOINT}/search', params=params)
        res.raise_for_status()
        return res.json()['features'][0]['geometry']['coordinates']
    except IndexError:
        return []


def reverse_geocode(location, focus=MOSCOW_CENTER, bbox=MMO_BBOX, max_occurrences=1):
    """"""
    try:
        lat, lon = location
        focus_lat, focus_lon = focus
        nw, se = bbox
        params = {
            'api_key': API_KEY,
            'point.lon': lon,
            'point.lat': lat,
            'layers': 'address',
            'sources': 'openstreetmap',
            'size': max_occurrences,
            'focus.point.lon': focus_lon,
            'focus.point.lat': focus_lat,
            'boundary.country': 'RU',
            'boundary.rect.min_lon': nw[1],
            'boundary.rect.min_lat': nw[0],
            'boundary.rect.max_lon': se[1],
            'boundary.rect.max_lat': se[0],
        }
        res = requests.get(f'{PELIAS_ENDPOINT}/reverse', params=params)
        res.raise_for_status()
        return res.json()['features'][0]['properties']['name']
    except IndexError:
        return ''


def suggest(text, focus=MOSCOW_CENTER, bbox=MMO_BBOX):
    """"""
    focus_lat, focus_lon = focus
    nw, se = bbox
    params = {
        'api_key': API_KEY,
        'text': text,
        'layers': 'address,venue',
        'sources': 'openstreetmap',
        'focus.point.lon': focus_lon,
        'focus.point.lat': focus_lat,
        'boundary.country': 'RU',
        'boundary.rect.min_lon': nw[1],
        'boundary.rect.min_lat': nw[0],
        'boundary.rect.max_lon': se[1],
        'boundary.rect.max_lat': se[0]
    }
    res = requests.get(f'{PELIAS_ENDPOINT}/autocomplete', params=params)
    res.raise_for_status()
    return [{
        'geometry': feature['geometry'],
        'properties': {
            'label': feature['properties']['label'],
            'distance': feature['properties']['distance'],
            'type': feature['properties']['layer']
        }
    } for feature in res.json()['features'] if feature['properties']['region'].startswith('Moscow')]
