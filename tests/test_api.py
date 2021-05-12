import pytest

from api.api import app


POSITION_VEREYSKAYA = '55.7109996,37.4362684'
POSITION_MKAD = '55.6259813,37.4744228'
POSITION_YASENEVAYA = '55.6023977,37.723043'


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
        'positions': ';'.join((POSITION_VEREYSKAYA, POSITION_YASENEVAYA)),
        'profile': 'driving-car'
    }
    res = client.get('/directions/', query_string=query_params)
    features = res.get_json().get('features')
    assert len(features) == 3  # factor out to some config


def test_directions_via(client):
    query_params = {
        'positions': ';'.join((POSITION_VEREYSKAYA, POSITION_MKAD, POSITION_YASENEVAYA)),
        'profile': 'driving-car'
    }
    res = client.get('/directions/', query_string=query_params)
    features = res.get_json().get('features')
    assert len(features) == 1
