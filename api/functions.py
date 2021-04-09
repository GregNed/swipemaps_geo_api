import requests


# API_KEY = '5b3ce3597851110001cf6248ec409dc3a99a42bc8a80b2f87c0da955'
# ORS_ENDPOINT = 'https://api.openrouteservice.org/'
ORS_ENDPOINT = 'http://localhost:8080'
MOSCOW_CENTER = (37.622311, 55.754801)


def geocode(text, focus=MOSCOW_CENTER, max_occurrences=5):
    """"""
    res = requests.get(
        ORS_ENDPOINT+'geocode/search',
        params={
            # 'api_key': API_KEY,
            'text': text,
            'layers': 'address,venue',
            'focus.point.lon': focus[0],
            'focus.point.lat': focus[1],
            'size': max_occurrences,
            'boundary.country': 'RU',
            'sources': 'openstreetmap'
        }
    )
    res.raise_for_status()
    return res.json()


def reverse_geocode(location, max_occurrences=5):
    """"""
    lon, lat = location
    res = requests.get(
        ORS_ENDPOINT+'geocode/reverse',
        params={
            # 'api_key': API_KEY,
            'point.lon': lon,
            'point.lat': lat,
            'layers': 'address',
            'size': max_occurrences,
            'boundary.country': 'RU',
            'sources': 'openstreetmap'
        }
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
