import requests


# API_KEY = '5b3ce3597851110001cf6248ec409dc3a99a42bc8a80b2f87c0da955'
# ORS_ENDPOINT = 'https://api.openrouteservice.org/'
ORS_ENDPOINT = 'http://localhost:8080'
PELIAS_ENDPOINT = 'http://localhost:4000/v1'
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


def geocode(text, focus=MOSCOW_CENTER, bbox=MMO_BBOX, max_occurrences=5):
    """"""
    params = {
        # 'api_key': API_KEY,
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
        # 'api_key': API_KEY,
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
        # 'api_key': API_KEY,
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


def route(start, end, mode='driving-car'):
    """"""
    res = requests.post(
        f'{ORS_ENDPOINT}v2/directions/{mode}',
        headers={
            # 'Authorization': API_KEY,
            'Content-Type': 'application/json'
        },
        json={
            'coordinates': [start, end],
            'alternative_routes': {
                'target_count': 3,
                'share_factor': 0.6,
                'weight_factor': 1.4
            }
        }
    )
    res.raise_for_status()
    return res.json()
