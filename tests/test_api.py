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
