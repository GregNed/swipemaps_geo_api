from uuid import uuid4

import pytest
from shapely.geometry import LineString, Point
from shapely.affinity import translate
from geoalchemy2.shape import to_shape

from app import app
from app.helpers import transform
from app.models import db, Route, PickupPoint, DropoffPoint


POSITIONS = [  # HEIDELBERG
    [49.4182041, 8.6765811],
    [49.4094651, 8.6928031],
    [49.3920971, 8.6860241]
] if app.testing else [  # MOSCOW
    [55.7607101, 37.5779111],  # Zoo
    [55.7586991, 37.6193321],  # Bolshoy Theater
    [55.7594871, 37.6258311]  # Lubyanka
]


def prepare_route(profile: str, user_id=None, trip_id=None, positions=POSITIONS, is_handled=False):
    """Pre-save a route to DB to perform further tests on it."""
    geog = LineString([position[::-1] for position in positions])
    attrs = {
        'user_id': user_id or uuid4(),
        'trip_id': trip_id,
        'profile': profile,
        'distance': 100.0,
        'duration': 10.0,
        'is_handled': is_handled
    }
    route = Route(id=uuid4(), geog=geog.wkt, **attrs)
    try:
        db.session.add(route)
        db.session.commit()
    except Exception as e:
        db.session.rollback()  # rollback to let other tests run
        raise e  # reraise to report the error
    return route


def validate_route(route: dict):
    """Check if a route has more than one segment and its distance & duration are > 0.

    Locations in this test suite are picked so that they always produce such a route if
    everything works fine. The route may change slightly as the underlying road data
    and the ORS version change, but it'll always produce a 'proper' route.

    This function is reused in several routing tests because something might break
    depending on the parameters used, so it seems that it's safer to validate the returned
    routes in each test.
    """
    # Exclude returning a straight line between the endpoints (for some reason)
    assert len(route['geometry']['coordinates']) > 2
    # Route distance & diration are present and they're floats (for Flutter to accept them)
    assert isinstance(route['properties']['distance'], float)
    assert isinstance(route['properties']['duration'], float)
    # Route distance & diration are > 0 (must be for the input route)
    assert route['properties']['distance'] > 0
    assert route['properties']['duration'] > 0


@pytest.fixture
def client():
    """Set up the Werkzeug test client and empty the DB afterwards."""
    with app.test_client() as client:
        yield client
    # # Clear the DB
    for model in (Route, PickupPoint, DropoffPoint):
        model.query.delete()
        db.session.commit()


def test_healthcheck(client):
    """API root returns each service's state as 'ok' or 'unavailable'."""
    response = client.get('/').get_json()
    for service in response:
        assert response[service] in ('ok', 'unavailable')


def test_routes_driver(client):
    """ORS paves sensible car routes."""
    body = {
        'positions': POSITIONS[:2],
        'profile': 'driving-car',
        'user_id': uuid4(),
        'alternatives': False,
        'handles': False,
        'make_route': True
    }
    response = client.post('/routes', json=body).get_json()
    route = response['routes']['features'][0]
    validate_route(route)


def test_routes_passenger(client):
    """Passenger routes aren't actually paved, but rather the endpoints are saved as a line.

    This is a test for passenger routes (!), and those are not the actual walking routes
    the passenger will ever walk. They're just their start and destination locations saved
    as a straight line.
    """
    positions = POSITIONS[:2]
    body = {
        'positions': positions,
        'profile': 'foot-walking',
        'user_id': uuid4(),
        'alternatives': False,
        'handles': False,
        'make_route': False  # do not pave an actual route via ORS
    }
    response = client.post('/routes', json=body).get_json()
    route = response['routes']['features'][0]
    route = Route.query.get(route['id'])
    # Assert the route has been stored as a straight line between the positions
    assert to_shape(route.geog).almost_equals(LineString(position[::-1] for position in positions))


def test_routes_alternatives(client):
    """ORS provides up to {config.ORS_MAX_ALTERNATIVES} alternative routes."""
    body = {
        'positions': POSITIONS[:2],
        'profile': 'driving-car',
        'user_id': uuid4(),
        'alternatives': True,
        'handles': True,
        'make_route': True
    }
    response = client.post('/routes', json=body).get_json()
    # Assert alternative routes are offered, as many as is set in the config
    assert (
        len(response['routes']['features']) ==
        len(response['handles']['features']) ==  # handles are offered in the same quantity
        app.config['ORS_MAX_ALTERNATIVES']
    )
    # Assert routes are valid (assume if one is valid, then all are)
    validate_route(response['routes']['features'][0])


def test_routes_via(client):
    """ORS paves routes via intermediate locations."""
    body = {
        'positions': POSITIONS,
        'profile': 'driving-car',
        'user_id': uuid4(),
        'alternatives': False,
        'handles': False,
        'make_route': True
    }
    route = client.post('/routes', json=body).get_json()['routes']['features'][0]
    validate_route(route)


def test_routes_prepared_trip_id(client):
    """Only routes with set trip ids are reused."""
    user_id = uuid4()
    positions = POSITIONS[:2]
    prepare_route('driving-car', user_id=user_id, positions=positions, is_handled=True)
    body = {
        'positions': positions,
        'profile': 'driving-car',
        'user_id': user_id,
        'alternatives': True,
        'handles': False,
        'make_route': True
    }
    response = client.post('/routes', json=body).get_json()
    assert len(response['prepared_routes']['features']) == 0


def test_routes_prepared_user_id(client):
    """Only the user's routes are reused."""
    positions = POSITIONS[:2]
    prepare_route('driving-car', trip_id=uuid4(), positions=positions, is_handled=True)
    body = {
        'positions': positions,
        'profile': 'driving-car',
        'user_id': uuid4(),
        'alternatives': True,
        'handles': False,
        'make_route': True
    }
    response = client.post('/routes', json=body).get_json()
    assert len(response['prepared_routes']['features']) == 0


def test_routes_prepared_identical(client):
    """Identical routes are reused; nothing breaks due to absence of tail and head."""
    user_id = uuid4()
    positions = POSITIONS[:2]
    prepare_route('driving-car', user_id=user_id, trip_id=uuid4(), positions=positions, is_handled=True)
    body = {
        'positions': positions,
        'profile': 'driving-car',
        'user_id': user_id,
        'alternatives': True,
        'handles': False,
        'make_route': True
    }
    response = client.post('/routes', json=body).get_json()
    assert len(response['prepared_routes']['features']) == 1


def test_routes_prepared_reverse(client):
    """Route direction is considered when reusing routes."""
    user_id = uuid4()
    prepare_route('driving-car', user_id=user_id, trip_id=uuid4(), positions=POSITIONS[1:None:-1], is_handled=True)
    body = {
        'positions': POSITIONS[:2],
        'profile': 'driving-car',
        'user_id': user_id,
        'alternatives': True,
        'handles': False,
        'make_route': True
    }
    response = client.post('/routes', json=body).get_json()
    assert len(response['prepared_routes']['features']) == 0


def test_routes_prepared_distant_start(client):
    """Route whose start is further than {config.POINT_PROXIMITY_THRESHOLD}."""
    user_id = uuid4()
    positions = POSITIONS[:2]
    prepare_route('driving-car', user_id=user_id, trip_id=uuid4(), positions=positions, is_handled=True)
    distant_start = translate(transform(Point(positions[0])), app.config['POINT_PROXIMITY_THRESHOLD'])
    body = {
        'positions': [list(transform(distant_start, to_wgs84=True).coords[0]), positions[1]],
        'profile': 'driving-car',
        'user_id': user_id,
        'alternatives': True,
        'handles': False,
        'make_route': True
    }
    response = client.post('/routes', json=body).get_json()
    assert len(response['prepared_routes']['features']) == 0


def test_routes_prepared_distant_finish(client):
    """Route whose finish is further than {config.POINT_PROXIMITY_THRESHOLD}."""
    user_id = uuid4()
    positions = POSITIONS[:2]
    prepare_route('driving-car', user_id=user_id, trip_id=uuid4(), positions=positions, is_handled=True)
    distant_finish = translate(transform(Point(positions[-1])), app.config['POINT_PROXIMITY_THRESHOLD'])
    body = {
        'positions': [positions[0], list(transform(distant_finish, to_wgs84=True).coords[0])],
        'profile': 'driving-car',
        'user_id': user_id,
        'alternatives': True,
        'handles': False,
        'make_route': True
    }
    response = client.post('/routes', json=body).get_json()
    assert len(response['prepared_routes']['features']) == 0


def test_get_route(client):
    """A route can be retrieved from the DB by its UUID."""
    route_in = prepare_route('driving-car', positions=POSITIONS)
    route_out = client.get(f'/routes/{route_in.id}').get_json()
    assert LineString(route_out['geometry']['coordinates']).almost_equals(to_shape(route_in.geog), decimal=3)
    assert str(route_in.id) == route_out['id']
    for attr in ('profile', 'user_id', 'distance', 'duration'):
        assert str(route_out['properties'][attr]) == str(getattr(route_in, attr))  # to serialize UUID
