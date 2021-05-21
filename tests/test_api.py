import pytest

from api.api import app

# MOSCOW
POSITION1 = '55.7109996,37.4362684'
POSITION2 = '55.6259813,37.4744228'
POSITION3 = '55.6023977,37.723043'
# HEIDELBERG
POSITION1 = '49.418204,8.676581'
POSITION2 = '49.409465,8.692803'
POSITION3 = '49.392097,8.686024'

# [8.676581, 49.418204], [8.692803, 49.409465]


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_healthcheck(client):
    res = client.get('/')
    assert res.get_json().get('status') == 'OK'


def test_directions(client):
    query_params = {
        'positions': ';'.join((POSITION1, POSITION2)),
        'profile': 'driving-car'
    }
    res = client.get('/directions/', query_string=query_params).get_json()
    routes = res['routes']['features']
    handles = res['handles']['features']
    assert len(routes) == len(handles) == 3  # factor out to some config


def test_directions_via(client):
    query_params = {
        'positions': ';'.join((POSITION1, POSITION2, POSITION3)),
        'profile': 'driving-car'
    }
    res = client.get('/directions/', query_string=query_params).get_json()
    routes = res['routes']['features']
    handles = res['handles']['features']
    assert len(routes) == len(handles) == 1
