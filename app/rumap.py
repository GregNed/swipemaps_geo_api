import os
from typing import Iterable

import requests
from flask import abort
from requests import HTTPError
from shapely.ops import linemerge

from app import app, helpers


RUMAP_ROUTING_URL = os.getenv('RUMAP_ROUTING_URL')
RUMAP_FORWARD_GEOCODING_URL = os.getenv('RUMAP_FORWARD_GEOCODING_URL')
RUMAP_REVERSE_GEOCODING_URL = os.getenv('RUMAP_REVERSE_GEOCODING_URL')
KEY = os.getenv('RUMAP_KEY')
SUPPORTED_CITIES = 'Иркутск', 'Йошкар-Ола', 'Алматы'
SUPPORTED_REGIONS = 'Москва', 'Московская'
HIERARCHY = {
    'address': {
        #  attribute is constructed separately
        'type': 'address',
        'parent': 'town'
    },
    'road': {
        'attribute': 'STFNM',
        'type': 'street',
        'parent': 'town'
    },
    'village': {
        'attribute': 'VLSNM',
        'type': 'settlement',
        'parent': 'admin'
    },
    'quarter': {
        'attribute': 'QTSNM',
        'type': 'area',
        'parent': 'town'
    },
    'district_t': {
        'attribute': 'DTFNM',
        'type': 'area',
        'parent': 'town'
    },
    'town': {
        'attribute': 'CTSNM',
        'type': 'settlement',
        'parent': 'admin'
    },
    'admin_2': {
        'attribute': 'A2FNM',
        'type': 'area',
        'parent': 'admin'
    },
    'district_a1': {
        'attribute': 'DA1FNM',
        'type': 'area',
        'parent': 'admin'
    },
    'admin1': {
        'attribute': 'A1FNM',
        'type': 'area',
        'parent': 'admin'
    },
    'district_a': {
        'attribute': 'DAFNM',
        'type': 'area',
        'parent': 'admin'
    },
    'admin': {
        'attribute': 'RFNM',
        'type': 'area',
        'parent': 'country'
    },
}


def directions(
    positions: list[list[float]],
    profile: str,
    alternatives: bool = False,
    geometry: bool = True
) -> list[dict]:
    positions = [{'x': position[0], 'y': position[1]} for position in positions]
    res = requests.post(
        RUMAP_ROUTING_URL + '/directions',
        params={'license': KEY},
        json={
            'vehicles': {'pedestrian' if profile == 'foot-walking' else 'car': {}},
            'points': positions,
            'routeAlternative': alternatives,
            'alternative': {
                'alternativeUpperLimitFactor': 1.4,
                'roadworksEnable': True
            },
            'speed': 'online',  # consider traffic
            'return': ['summary'] + (['geometry'] if geometry else []),
            'startingedgescount': 1,  # temp bug fix: awaits to be resolved by GeoCenter
            'endingedgescount': 1,  # temp bug fix: awaits to be resolved by GeoCenter
        }
    )
    try:
        res.raise_for_status()
    except HTTPError as e:
        if res.status_code == 403:  # KEY expired or out of quota
            app.config['GEO_ENGINE'] = 'ors'
        raise e  # re-raise to submit the same request to ORS
    res = res.json()
    if not alternatives:
        res = [res]  # wrap single feature in a list for consistency
    try:
        routes = [{
            'geometry': linemerge([
                feature['geometry']['coordinates']
                for feature in route['features']
                if feature['geometry']['type'] == 'LineString'
            ]),
            'distance': float(route['properties']['length']),
            'duration': float(route['properties']['time']),
            'source': app.config['GEO_ENGINE']
        } for route in res]
    except KeyError:
        routes = [{
            'geometry': positions,
            'distance': 0.0,
            'duration': 0.0
        } for route in res]
    return routes or abort(500, 'Rumap failed to route between the requested locations')


def parse(properties: dict) -> dict:
    """"""
    if properties['dataType'] == 'poi':
        address = properties['NAME']
        locality = properties['ADDRESS']
        type_ = 'poi'
    else:
        type_ = HIERARCHY[properties['type']]['type']
        try:
            parent: str = HIERARCHY[properties['type']]['parent']
            locality = properties[HIERARCHY[parent]['attribute']]
        except KeyError:
            locality = '' if properties['type'] == 'admin' else properties.get('RFNM')
        if properties['type'] == 'address':
            address = (
                properties['STFNM'] + ' ' +
                properties.get('A_NUM', '') +
                properties.get('A_ELT1', '').lower() +
                properties.get('A_NUMLET1', '')
            )
        elif properties['type'] == 'road':
            address = properties['STFNM']
        else:  # admin unit e.g. neighborhood, district, county
            address = properties[HIERARCHY[properties['type']]['attribute']] or properties.get('RFNM')
    return {
        'address': address,
        'locality': locality,
        'type': type_
    }


def geocode(text: str, mode: str, count: int, focus: Iterable):
    """"""
    res = requests.get(
        url=RUMAP_FORWARD_GEOCODING_URL + '/' + mode,
        params={
            'guid': KEY,
            'text': text,
            'format': 'geojson:full',
            'count': count,
            'x': focus[0],
            'y': focus[1],
        }
    )
    try:
        res.raise_for_status()
    except HTTPError as e:
        if res.status_code == 403:  # rumap KEY has expired or out of quota
            app.config['GEO_ENGINE'] = 'ors'  # switch to ORS
        raise e  # re-raise for the route handler to retry using ORS
    results = sorted(
        res.json()['features'],
        key=lambda i: i['properties']['accuracy'],
        reverse=True
    )[:count]
    return [
        {
            'id': id_,
            'geometry': feature['geometry'],
            'properties': {
                **parse(feature['properties']),
                'distance': round(helpers.haversine(focus, feature['geometry']['coordinates']))
            }
        }
        for id_, feature in enumerate(results, start=1)
        if feature['properties']['dataType'] == 'poi' or (
            feature['properties']['type'] in HIERARCHY and (
                feature['properties'].get('RSNM') in SUPPORTED_REGIONS
                or feature['properties'].get('CTSNM') in SUPPORTED_CITIES
            )
        )
    ]


def reverse_geocode(location: Iterable, focus: Iterable) -> dict:
    """Kwargs added so that focus point can be passed just as w/ ORS w/out raising an error."""
    res = requests.get(
        url=RUMAP_REVERSE_GEOCODING_URL + '/getAddress',
        params={
            'guid': KEY,
            'x': location[0],
            'y': location[1],
            'format': 'geojson:full',
        }
    )
    try:
        res.raise_for_status()
    except HTTPError as e:
        if res.status_code == 403:  # KEY expired or out of quota
            app.config['GEO_ENGINE'] = 'ors'
        raise e  # re-raise to submit the same request to ORS
    feature = res.json()['features'][0]
    if feature['properties']['type'] in HIERARCHY and (
        feature['properties'].get('RSNM') in SUPPORTED_REGIONS
        or feature['properties'].get('CTSNM') in SUPPORTED_CITIES
    ):
        feature['id'] = 1
        feature['properties'] = {
            **parse(feature['properties']),
            'distance': round(helpers.haversine(focus, feature['geometry']['coordinates']))
        }
        return feature
    else:
        abort(404, 'Nothing found; try a different text')
