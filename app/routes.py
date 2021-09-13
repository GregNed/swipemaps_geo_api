from uuid import uuid4

import numpy as np
import sqlalchemy
from sqlalchemy import func
from shapely.geometry import Point, LineString, MultiPoint
from shapely.ops import nearest_points, substring, snap, linemerge, unary_union
from geojson import Feature, FeatureCollection
from flask import request, abort
from geoalchemy2.shape import to_shape

from app import app, db, ors
from app.models import DropoffPoint, Route, PickupPoint, PublicTransportStop
from app.helpers import transform, haversine, route_to_feature, PROJECTION


ROUTE_NOT_FOUND_MESSAGE = 'No such route in the database :-('


def healthcheck():
    response = {service: 'ok' for service in ('server', 'postgres', 'ors', 'pelias')}
    try:
        Route.query.first()
    except sqlalchemy.exc.OperationalError:
        response['postgres'] = 'unavailable'
    try:
        ors.directions([[37.619188, 55.759128], [37.626247, 55.759426]], 'driving-car')
    except:
        response['ors'] = 'unavailable'
    try:
        ors.geocode('Тверская 1')
    except:
        response['pelias'] = 'unavailable'
    return response


def get_stops(bbox):
    if bbox:
        min_lat, min_lon, max_lat, max_lon = map(float, bbox.split(','))
        stops = PublicTransportStop.query.filter(
            func.ST_Intersects(
                PublicTransportStop.geom,
                func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, '4326')
            )
        )
    else:
        stops = PublicTransportStop.query.all()
    return FeatureCollection([
        Feature(stop.id, to_shape(stop.geom), {'name': stop.name}) for stop in stops
    ])


def distance():
    return round(haversine(*request.json['positions']))


def get_route_start_or_finish(route_id, point):
    index = 0 if point == 'start' else -1
    route = to_shape(Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).geog)
    return list(route.coords[index])  # returning a tuple, as provided by Shapely, will raise an error


def is_passenger_arrived(route_id, position):
    route = to_shape(Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).geog)
    driver_position = Point(map(float, position.split(',')[::-1]))
    return transform(driver_position).distance(transform(route)) < app.config['DROPOFF_RADIUS']


def get_pickup_point(route_id):
    point = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).pickup_point
    return list(to_shape(point.geog).coords[0]) if point else (f'Route {route_id} has no pick-up point', 204)


def post_pickup_point(route_id):
    geog = Point(request.json['position'][::-1]).wkt
    route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    if route.profile == 'driving-car':
        abort(400, 'Only passenger routes can have pick-up points')
    point = PickupPoint.query.filter(PickupPoint.route_id == route_id).first()
    if point:
        point.geog = geog
    else:
        point = PickupPoint(id=uuid4(), geog=geog, route_id=route_id)
        db.session.add(point)
    db.session.commit()
    return point.id, 201


def get_dropoff_point(route_id):
    point = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).dropoff_point
    return list(to_shape(point.geog).coords[0]) if point else (f'Route {route_id} has no drop-off point', 204)


def post_dropoff_point(route_id):
    geog = Point(request.json['position'][::-1]).wkt
    route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    if route.profile == 'driving-car':
        abort(400, 'Only passenger routes can have drop-off points')
    point = DropoffPoint.query.filter(DropoffPoint.route_id == route_id).first()
    if point:
        point.geog = geog
    else:
        point = DropoffPoint(id=uuid4(), geog=geog, route_id=route_id)
        db.session.add(point)
    db.session.commit()
    return point.id, 201


def immitate(route_id):
    route = transform(to_shape(Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).geog))
    route_coords = np.array(route.coords)
    route_coords_delta = np.random.uniform(-20.0, 20.0, (len(route_coords), 2))
    route_coords += route_coords_delta
    points = [transform(Point(position[::-1])) for position in request.json['positions']]
    route_vertices = MultiPoint(route_coords)
    points_snapped = [nearest_points(route_vertices, point)[0].coords[0] for point in points]
    for new, old in zip(points, points_snapped):
        route_coords = np.where(route_coords == old, new, route_coords)
    return Feature(geometry=transform(LineString(route_coords), to_wgs84=True))


def remainder(route_id, position):
    driver_route = to_shape(Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).geog)
    current_position = Point(map(float, position.split(',')[::-1]))
    current_position_snapped = nearest_points(driver_route, current_position)[0]
    route_passed_fraction = driver_route.project(current_position_snapped, normalized=True)
    remaining_route = substring(driver_route, route_passed_fraction, 1, normalized=True)
    return list(remaining_route.coords)


def suggest_pickup(route_id, position):
    driver_route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).geog
    driver_route_projected = transform(to_shape(driver_route))
    passenger_start = Point(map(float, position.split(',')[::-1]))
    # Project it for Shapely calculations
    passenger_start_projected = transform(passenger_start)
    # Reassign it for PostGIS calculations
    passenger_start = func.ST_GeogFromText(passenger_start.wkt)
    # Retrieve the relevant public transport stops
    public_transport_stop_geom = func.ST_GeogFromWKB(func.ST_AsBinary(PublicTransportStop.geom))
    stops = PublicTransportStop.query.filter(
        func.ST_DWithin(public_transport_stop_geom, driver_route, 50, use_spheroid=False),
        func.ST_DWithin(public_transport_stop_geom, passenger_start, 1000, use_spheroid=False)
    )
    # Identify the closest point on the driver's route
    nearest_point = nearest_points(driver_route_projected, passenger_start_projected)[0]
    driver_route_start = Point(driver_route_projected.coords[0])
    if driver_route_start.distance(nearest_point) < 500:  # just meet driver at their start
        nearest_point = transform(driver_route_start, to_wgs84=True)
    elif stops:
        nearest_point = to_shape(stops.order_by(
            func.ST_Distance(PublicTransportStop.geom, passenger_start)
        ).first().geom)
    return {
        'nearest_point': Feature(geometry=nearest_point),
        'stops': FeatureCollection([Feature(geometry=to_shape(stop.geom)) for stop in stops])
    }


def route_walking(route_id):
    """"""
    route = to_shape(Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).geog)
    position = request.json['position'][::-1]  # lat, lon -> lon, lat
    nearest_point, _ = nearest_points(route, Point(position))
    positions = [position, nearest_point.coords[0]]
    if request.json['to_or_from'] == 'from':
        positions.reverse()
    route = ors.directions(positions, 'foot-walking')[0]
    route_id = uuid4()
    db.session.add(Route(
        id=route_id,
        user_id=request.json['user_id'],
        profile='foot-walking',
        geog=LineString(route['geometry']).wkt,
        distance=route['distance'],
        duration=route['duration']
    ))
    db.session.commit()
    return Feature(id=route_id, geometry=LineString(route['geometry']), properties={
        'distance': route['distance'],
        'duration': route['duration']
    })


def routes():
    """"""
    # Convert start, end and intermediate points from [lat, lon] to [lon, lat] format used in ORS & Shapely
    positions = [position[::-1] for position in request.json['positions']]
    if len(set(str(position) for position in positions)) != len(positions):
        abort(400, 'Request contains duplicate positions')
    # Start & end will mostly be manipulated via Shapely, so turn them into shapes
    start, finish = Point(positions[0]), Point(positions[-1])
    # Reproject them to be used with Shapely (leave the spherical versions to save to the DB later)
    start_projected, finish_projected = transform(start), transform(finish)
    prepared_routes, handles = [], []
    with_alternatives = request.json.get('alternatives', True) and len(positions) == 2
    with_handles = request.json.get('handles', True)
    # Order intermediate positions along the route
    if len(positions) > 2:
        positions.sort(key=lambda x: start_projected.distance(transform(Point(x))))
    # Check if there are similar routes in the user's history; if there are any, return them along w/ the new ones
    if with_alternatives:
        # Prepare PostGIS functions for analysis
        route_projected = func.ST_Transform(func.ST_GeomFromWKB(Route.geog, '4326'), PROJECTION)
        route_start = func.ST_StartPoint(route_projected)
        route_finish = func.ST_EndPoint(route_projected)
        # Get all the routes from the user's history
        past_routes = Route.query.filter(
            Route.user_id == request.json['user_id'],
            Route.is_handled,
            Route.trip_id != None,
            func.ST_Distance(route_start, func.ST_GeomFromText(start_projected.wkt, PROJECTION))
            < app.config['POINT_PROXIMITY_THRESHOLD'],
            func.ST_Distance(route_finish, func.ST_GeomFromText(finish_projected.wkt, PROJECTION))
            < app.config['POINT_PROXIMITY_THRESHOLD']
        ).limit(app.config['MAX_PREPARED_ROUTES'])
        for route in past_routes:
            # Convert common part bc the other parts will be returned from ORS as dict
            route = {
                'geometry': transform(to_shape(route.geog)),
                'distance': route.distance,
                'duration': route.duration
            }
            # Get the closest points on the past route to counterparts requested by the user
            nearest_to_start, _ = nearest_points(route['geometry'], start_projected)
            nearest_to_finish, _ = nearest_points(route['geometry'], finish_projected)
            # Reproject them back to WGS84 for the ORS
            nearest_to_start_4326 = transform(nearest_to_start, to_wgs84=True).coords[0]
            nearest_to_finish_4326 = transform(nearest_to_finish, to_wgs84=True).coords[0]
            # Extract the relevant part of the past route
            cut_point_distances = [route['geometry'].project(pt) for pt in (nearest_to_start, nearest_to_finish)]
            route['geometry'] = substring(route['geometry'], *cut_point_distances)
            # A tail is from the start to the point closest to the start, a head - likewise but from the finish
            tail = ors.directions([positions[0], nearest_to_start_4326], request.json['profile'])[0]
            head = ors.directions([nearest_to_finish_4326, positions[-1]], request.json['profile'])[0]
            parts_to_merge = [route]  # tail and head will get added if they prove non-empty
            for part in (tail, head):
                try:
                    part['geometry'] = transform(LineString(part['geometry']).simplify(0))
                except ValueError:  # part['geometry'] contains < 2 positions
                    continue
                # Remove duplicate segments
                part['geometry'] = LineString([
                    snap(Point(coords), nearest_points(route['geometry'], Point(coords))[0], 25)
                    for coords in part['geometry'].coords
                ])
                # Remove overlapping parts
                if part['geometry'].overlaps(route['geometry']) and not part['geometry'].within(route['geometry']):
                    part['geometry'], route['geometry'] = part['geometry'].symmetric_difference(route['geometry'])
                    parts_to_merge.append(part)  # is a proper part, add to list for merging
            # Stitch the parts together if there is a tail or a head, or both
            if len(parts_to_merge) > 1:
                full_route = linemerge(unary_union([part['geometry'] for part in parts_to_merge]))
            else:
                full_route = route['geometry']
            prepared_routes.append({
                'geometry': transform(full_route, to_wgs84=True).coords,
                'distance': sum(part['distance'] for part in parts_to_merge),
                'duration': sum(part['duration'] for part in parts_to_merge)
            })
    # User may opt to drive ad-hoc w/out preparing a route; if make_route is False, only the end points will be saved
    if request.json.get('make_route') is False:
        route_id = uuid4()
        db.session.add(Route(
            id=route_id,
            user_id=request.json['user_id'],
            profile=request.json['profile'],
            geog=LineString([start, finish]).wkt
        ))
        routes = FeatureCollection([Feature(id=route_id, geometry=LineString([start, finish]))])
    else:
        routes = ors.directions(positions, request.json['profile'], with_alternatives)
        # Save routes to DB
        all_routes = routes + prepared_routes
        route_ids = [uuid4() for _ in all_routes]
        for route, route_id in zip(all_routes, route_ids):
            db.session.add(Route(
                id=route_id,
                user_id=request.json['user_id'],
                profile=request.json['profile'],
                distance=route['distance'],
                duration=route['duration'],
                geog=LineString(route['geometry']).wkt,
                is_handled=(with_handles and len(positions) > 2)
            ))
        if request.json['profile'] == 'driving-car' and with_handles:
            # Get midpoints of the route's last segment for the user to drag on the screen
            routes_last_parts = routes if with_alternatives else ors.directions(positions[-2:], request.json['profile'])
            routes_last_parts = [route['geometry'] for route in routes_last_parts]
            handles = [LineString(route).interpolate(0.5, normalized=True) for route in routes_last_parts]
            handles = [Point(handle.coords[0]) for handle in handles]
            handles = FeatureCollection([Feature(route_id, handle) for route_id, handle in zip(route_ids, handles)])
        # Prepare the response
        routes, prepared_routes = [
            FeatureCollection([
                Feature(
                    id=route_id,
                    geometry=LineString(route['geometry']),
                    properties={attr: route[attr] for attr in ('distance', 'duration')}
                ) for route_id, route in zip(route_ids, route_set)
            ]) for route_set in (routes, prepared_routes)
        ]
    db.session.commit()
    return {
        'routes': routes,
        'handles': handles if with_handles else [],
        'prepared_routes': prepared_routes if with_alternatives else [],
    }


def get_route(route_id):
    route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    return route_to_feature(route)


def delete_discarded_routes(route_id, user_id):
    count = Route.query.filter(
        Route.user_id == user_id,
        Route.id != route_id,
        Route.trip_id == None
    ).delete()
    if count == 0:
        abort(404, 'User and route combination not found')
    Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).trip_id = request.json['trip_id']
    try:
        db.session.commit()
    except sqlalchemy.exc.IntegrityError as e:
        db.session.rollback()
        abort(400, 'Such trip id already exists in the database')
    except Exception as e:
        db.session.rollback()
        abort(500, str(e))


def get_candidates(route_id):
    target_route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    target_start = func.ST_StartPoint(func.ST_GeomFromWKB(target_route.geog))
    target_finish = func.ST_EndPoint(func.ST_GeomFromWKB(target_route.geog))
    candidate_route_ids = request.json['candidate_route_ids']
    candidate_start = func.ST_StartPoint(func.ST_GeomFromWKB(Route.geog))
    candidate_finish = func.ST_EndPoint(func.ST_GeomFromWKB(Route.geog))
    candidate_routes = Route.query.filter(
        Route.id.in_(candidate_route_ids),
        Route.user_id != target_route.user_id,
        func.ST_Distance(candidate_start, target_route.geog) < app.config['CANDIDATE_DISTANCE_LIMIT'],
        func.ST_Distance(candidate_finish, target_route.geog) < app.config['CANDIDATE_DISTANCE_LIMIT'],
        func.ST_Distance(candidate_finish, target_finish) < func.ST_Distance(candidate_start, target_finish)
    )
    if target_route.profile == 'foot-walking':
        candidate_routes = candidate_routes.filter(Route.trip_id != None)
    # Define attributes & weights for sorting: (candidate_route, target_route, weight)
    sortings = {
        'driving-car': (
            (candidate_start, target_start, .35),
            (candidate_finish, target_finish, .35),
            (candidate_start, target_route.geog, .15),
            (candidate_finish, target_route.geog, .15)
        ),
        'foot-walking': (
            (candidate_start, target_start, .35),
            (candidate_finish, target_finish, .35),
            (Route.geog, target_start, .15),
            (Route.geog, target_finish, .15)
        )
    }
    candidate_routes.order_by(sum([
        func.ST_Distance(from_, to_) * weight
        for from_, to_, weight in sortings[target_route.profile]
    ]))
    return [route.id for route in candidate_routes]


def geocode(text):
    result = ors.geocode(text)
    if result:
        return result
    else:
        abort(404, 'Nothing found; try a different text')


def reverse_geocode(position):
    address = ors.reverse_geocode(map(float, position.split(',')))
    if address:
        return address
    else:
        abort(404, 'Nothing found')


def suggest(text):
    result = ors.suggest(text)
    if result:
        return FeatureCollection(
            [Feature(
                geometry=feature['geometry'],
                properties=feature['properties']
            ) for feature in result]
        )
    else:
        abort(404, 'Nothing found; try a different text')
