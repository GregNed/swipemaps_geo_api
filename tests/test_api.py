import pytest

from api.api import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_healthcheck(client):
    res = client.get('/')
    assert res.get_json().get('status') == 'OK'


def test_directions(client):
    res = client.get('/directions/?positions=55.7109996,37.4362684;55.6023977,37.723043&profile=driving-car')
    features = res.get_json().get('features')
    assert len(features) == 3  # factor out to some config


def test_directions_via(client):
    res = client.get('/directions/?55.7109996,37.4362684;55.6259813,37.4744228;55.6023977,37.723043&profile=driving-car')
    features = res.get_json().get('features')
    assert len(features) == 1
