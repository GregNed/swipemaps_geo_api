from uuid import uuid4
from requests.models import HTTPError

import sqlalchemy
from sqlalchemy import func
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points, substring, snap, linemerge, unary_union
from geojson import Feature, FeatureCollection
from flask import request, abort
from geoalchemy2.shape import from_shape, to_shape

from app import app, db, ors, rumap
from app.models import DropoffPoint, Route, PickupPoint, PublicTransportStop, Aoi, Road
from app.helpers import project, to_wgs84, haversine, route_to_feature, parse_lat_lon


PROJECTION = app.config['PROJECTION']  # to save some typing and avoid typos
ROUTE_NOT_FOUND_MESSAGE = 'No such route in the database :-('
MOSCOW_CENTER = '55.754801,37.622311'  # default focus point


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


def get_roads(position, radius):
    position = project(Point(parse_lat_lon(position)))
    roads = Road.query.filter(func.ST_DWithin(Road.geom, from_shape(position, PROJECTION), radius))
    return FeatureCollection([
        Feature(
            road.id,
            to_wgs84(to_shape(road.geom)),
            {'name': road.name, 'type': road.type}
        ) for road in roads
    ])


def get_areas():
    areas = Aoi.query.all()
    return {
        'polygons': FeatureCollection([
            Feature(area.id, to_wgs84(to_shape(area.geom)), {'name': area.name}) for area in areas
        ]),
        'points': FeatureCollection([
            Feature(area.id, to_wgs84(to_shape(area.geom).centroid), {'name': area.name}) for area in areas
        ])
    }


def get_stops(bbox):
    if bbox:
        # Parse the coords
        min_lat, min_lon, max_lat, max_lon = map(float, bbox.split(','))
        # Project the coords
        min_lon, min_lat = project(Point(min_lon, min_lat)).coords[0]
        max_lon, max_lat = project(Point(max_lon, max_lat)).coords[0]
        # Query
        bbox = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, PROJECTION)
        stops = PublicTransportStop.query.filter(func.ST_Intersects(PublicTransportStop.geom, bbox))
    else:
        stops = PublicTransportStop.query.all()
    return FeatureCollection([
        Feature(stop.id, to_wgs84(to_shape(stop.geom)), {'name': stop.name})
        for stop in stops
    ])


def get_route_start_or_finish(route_id, point):
    index = 0 if point == 'start' else -1
    route = to_shape(Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).geom)
    endpoint_wgs84 = to_wgs84(Point(route.coords[index]))
    return list(endpoint_wgs84.coords[0])  # returning a tuple, as provided by Shapely, raises an error


def is_passenger_arrived(route_id, position):
    route = to_shape(Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).geom)
    driver_position = project(Point(parse_lat_lon(position)))
    return driver_position.distance(route) < app.config['DROPOFF_RADIUS']


def get_pickup_point(route_id):
    point = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).pickup_point
    if point:
        return list(to_wgs84(to_shape(point.geom)).coords[0])
    return (f'Route {route_id} has no pick-up point', 204)


def delete_pickup_point(route_id):
    point = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).pickup_point
    if point:
        db.session.delete(point)
        db.session.commit()
    else:
        abort(404, f'Route {route_id} has no pick-up point')


def post_pickup_point(route_id):
    geom = project(Point(request.json['position'][::-1])).wkt
    route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    if route.profile == 'driving-car':
        abort(400, 'Only passenger routes can have pick-up points')
    point = PickupPoint.query.filter(PickupPoint.route_id == route_id).first()
    if point:
        point.geom = geom
    else:
        point = PickupPoint(id=uuid4(), geom=geom, route_id=route_id)
        db.session.add(point)
    db.session.commit()
    return point.id, 201


def get_dropoff_point(route_id):
    point = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).dropoff_point
    if point:
        return list(to_wgs84(to_shape(point.geom)).coords[0])
    return (f'Route {route_id} has no drop-off point', 204)


def post_dropoff_point(route_id):
    geom = project(Point(request.json['position'][::-1])).wkt
    route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    if route.profile == 'driving-car':
        abort(400, 'Only passenger routes can have drop-off points')
    point = DropoffPoint.query.filter(DropoffPoint.route_id == route_id).first()
    if point:
        point.geom = geom
    else:
        point = DropoffPoint(id=uuid4(), geom=geom, route_id=route_id)
        db.session.add(point)
    db.session.commit()
    return point.id, 201


def get_remainder(route_id):
    remainder = Route.query.get_or_404(route_id).geom_remainder
    return Feature(route_id, to_wgs84(to_shape(remainder)), {'distance': round(remainder.length)})


def post_remainder(route_id):
    route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    route_geom = to_shape(route.geom)
    current_position = project(Point(request.json['position'][::-1]))
    current_position_snapped = nearest_points(route_geom, current_position)[0]
    route_passed_fraction = route_geom.project(current_position_snapped, normalized=True)
    remainder = substring(route_geom, route_passed_fraction, 1, normalized=True)
    route.geom_remainder = from_shape(remainder)
    db.session.commit()
    return Feature(route_id, to_wgs84(remainder), {'distance': round(remainder.length)})


def suggest_pickup(route_id, position):
    driver_route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).geom
    driver_route_shape = to_shape(driver_route)
    passenger_start = project(Point(parse_lat_lon(position)))
    # Identify the closest point on the driver's route
    nearest_point = nearest_points(driver_route_shape, passenger_start)[0]
    radius = min(passenger_start.distance(nearest_point), app.config['PICKUP_MAX_RADIUS'])
    radius = max(radius, app.config['PICKUP_MIN_RADIUS'])
    # Retrieve the relevant public transport stops
    stops = PublicTransportStop.query.filter(
        func.ST_DWithin(PublicTransportStop.geom, from_shape(nearest_point, PROJECTION), radius)
    )
    return {
        'radius': radius,
        'nearest_point': Feature(geometry=to_wgs84(nearest_point)),
        'stops': FeatureCollection([Feature(geometry=to_wgs84(to_shape(stop.geom))) for stop in stops]),
    }


def walking_route(route_id):
    """"""
    route = to_shape(Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE).geom)
    position = request.json['position'][::-1]  # lat, lon -> lon, lat
    nearest_point = to_wgs84(nearest_points(route, project(Point(position)))[0]).coords[0]
    positions = [position, nearest_point]
    if request.json['to_or_from'] == 'from':
        positions.reverse()
    route = ors.directions(positions, 'foot-walking')[0]
    if request.json['to_or_from'] == 'to':
        route['geometry'].append(nearest_point)
    else:
        route['geometry'].insert(0, nearest_point)
    route_id = uuid4()
    route_geom = project(LineString(route['geometry'])).wkt
    db.session.add(Route(
        id=route_id,
        user_id=request.json['user_id'],
        profile='foot-walking',
        geom=route_geom,
        geom_remainder=route_geom,
        distance=route['distance'],
        duration=route['duration']
    ))
    db.session.commit()
    return Feature(
        id=route_id,
        geometry=LineString(route['geometry']),
        properties={
            'distance': route['distance'],
            'duration': route['duration']
        })


def post_route():
    """"""
    # Convert start, end and intermediate points from [lat, lon] to [lon, lat] format used in ORS & Shapely
    positions = [position[::-1] for position in request.json['positions']]
    if len(set(str(position) for position in positions)) != len(positions):
        abort(400, 'Request contains duplicate positions')
    # Start & end will mostly be manipulated via Shapely, so turn them into shapes
    start, finish = Point(positions[0]), Point(positions[-1])
    # Reproject them to be used with Shapely (leave the spherical versions to save to the DB later)
    start_projected, finish_projected = project(start), project(finish)
    prepared_routes, prepared_route_buffers, handles = [], [], []
    with_alternatives = request.json.get('alternatives', True) and len(positions) == 2 and request.json['profile'] == 'driving-car'
    with_handles = request.json.get('handles', True)
    # Order intermediate positions along the route
    if len(positions) > 2:
        positions.sort(key=lambda position: start_projected.distance(project(Point(position))))
    # Check if there are similar routes in the user's history; if there are any, return them along w/ the new ones
    if with_alternatives:
        # Get all the routes from the user's history
        past_routes = Route.query.filter(
            Route.user_id == request.json['user_id'],  # only same user's routes
            Route.is_handled,  # only those built using handles
            Route.trip_id != None,  # only actually driven routes
            func.ST_Distance(  # starts aren't further apart than ...
                func.ST_StartPoint(Route.geom),
                from_shape(start_projected, PROJECTION)
            ) < app.config['POINT_PROXIMITY_THRESHOLD'],
            func.ST_Distance(  # finishes aren't further apart than ...
                func.ST_EndPoint(Route.geom),
                from_shape(finish_projected, PROJECTION)
            ) < app.config['POINT_PROXIMITY_THRESHOLD']
        ).order_by(Route.created_at.desc()).limit(app.config['MAX_PREPARED_ROUTES'])  # only latest
        for route in past_routes:
            # Convert common part bc the other parts will be returned from ORS as dict
            route = {
                'geometry': to_shape(route.geom),
                'distance': route.distance,
                'duration': route.duration
            }
            # Get the closest points on the past route to counterparts requested by the user
            nearest_to_start, _ = nearest_points(route['geometry'], start_projected)
            nearest_to_finish, _ = nearest_points(route['geometry'], finish_projected)
            # Reproject them back to WGS84 for the ORS
            nearest_to_start_4326 = to_wgs84(nearest_to_start).coords[0]
            nearest_to_finish_4326 = to_wgs84(nearest_to_finish).coords[0]
            # Extract the relevant part of the past route
            cut_point_distances = (route['geometry'].project(pt) for pt in (nearest_to_start, nearest_to_finish))
            route['geometry'] = substring(route['geometry'], *cut_point_distances)
            # A tail is from the start to the point closest to the start, a head - likewise but from the finish
            tail = ors.directions([positions[0], nearest_to_start_4326], request.json['profile'])[0]
            head = ors.directions([nearest_to_finish_4326, positions[-1]], request.json['profile'])[0]
            parts_to_merge = [route]  # tail and head will get added if they prove non-empty
            for part in tail, head:
                try:
                    part['geometry'] = project(LineString(part['geometry']).simplify(0))
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
                'geometry': to_wgs84(full_route).coords,
                'distance': sum(part['distance'] for part in parts_to_merge),
                'duration': sum(part['duration'] for part in parts_to_merge)
            })
            prepared_route_buffers.append(
                route['geometry'].buffer(app.config['ROUTE_BUFFER_SIZE'], cap_style=2)
            )
    # User may opt to drive ad-hoc w/out preparing a route; if make_route is False, only the end points will be saved
    if request.json.get('make_route') is False:
        route_id = uuid4()
        route_wgs84 = LineString([start, finish])
        route_geom = project(route_wgs84).wkt
        db.session.add(Route(
            id=route_id,
            user_id=request.json['user_id'],
            profile=request.json['profile'],
            geom=route_geom,
            geom_remainder=route_geom
        ))
        routes = FeatureCollection([Feature(route_id, route_wgs84)])
        route_buffers = FeatureCollection([
            Feature(route_id, to_wgs84(
                project(route_wgs84).buffer(app.config['ROUTE_BUFFER_SIZE'], cap_style=2)
            ))
        ])
    else:
        routing_engine = globals()[app.config['GEO_ENGINE']]
        routes = routing_engine.directions(positions, request.json['profile'], with_alternatives)
        # Save routes to DB
        all_routes = routes + prepared_routes
        route_ids = [uuid4() for _ in all_routes]
        for route, route_id in zip(all_routes, route_ids):
            route_geom = project(LineString(route['geometry'])).wkt
            db.session.add(Route(
                id=route_id,
                user_id=request.json['user_id'],
                profile=request.json['profile'],
                distance=route['distance'],
                duration=route['duration'],
                geom=route_geom,
                geom_remainder=route_geom,
                is_handled=(with_handles and len(positions) > 2)
            ))
        if request.json['profile'] == 'driving-car' and with_handles:
            # Get midpoints of the route's last segment for the user to drag on the screen
            routes_last_parts = routes if with_alternatives else routing_engine.directions(positions[-2:], request.json['profile'])
            routes_last_parts = (route['geometry'] for route in routes_last_parts)
            handles = [LineString(route).interpolate(0.5, normalized=True) for route in routes_last_parts]
            handles = [Point(handle.coords[0]) for handle in handles]
            handles = FeatureCollection([Feature(id_, handle) for id_, handle in zip(route_ids, handles)])
        # Prepare the response
        route_buffers = FeatureCollection([
            Feature(id_, to_wgs84(
                project(LineString(route['geometry']))
                .buffer(app.config['ROUTE_BUFFER_SIZE'], cap_style=2)
            ))
            for id_, route in zip(route_ids, routes)
        ])
        prepared_route_buffers = FeatureCollection([
            Feature(id_, buffer) for id_, buffer in zip(route_ids, prepared_route_buffers)
        ])
        routes, prepared_routes = [
            FeatureCollection([
                Feature(
                    id=id_,
                    geometry=LineString(route['geometry']),
                    properties={attr: route[attr] for attr in ('distance', 'duration')}
                ) for id_, route in zip(route_ids, route_set)
            ]) for route_set in (routes, prepared_routes)
        ]
    db.session.commit()
    return {
        'routes': routes,
        'handles': handles if with_handles else [],
        'prepared_routes': prepared_routes if with_alternatives else [],
        'route_buffers': route_buffers,
        'prepared_route_buffers': prepared_routes if with_alternatives else []
    }


def get_route(route_id):
    route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    return route_to_feature(route)


def put_route(route_id):
    route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    if request.json.get('trip_id'):
        route.trip_id = request.json['trip_id']
    if request.json.get('positions'):
        positions = [position[::-1] for position in request.json['positions']]
        new_route = ors.directions(positions, 'driving-car')[0]
        route_geom = LineString(new_route['geometry'])
        route.geom = route.geom_remainder = project(route_geom).wkt
        route.distance = new_route['distance']
        route.duration = new_route['duration']
    try:
        db.session.commit()
    except sqlalchemy.exc.IntegrityError:
        db.session.rollback()
        abort(400, 'Such trip id already exists in the database')
    except Exception as e:
        db.session.rollback()
        abort(500, str(e))
    return Feature(
        route_id,
        route_geom,
        {
            'distance': route.distance,
            'duration': route.duration
        }
    ) if request.json.get('positions') else ('', 204)


def delete_route(route_id):
    route = Route.query.get_or_404(route_id)
    db.session.delete(route)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(500, str(e))


def get_candidates(route_id):
    target_route = Route.query.get_or_404(route_id, ROUTE_NOT_FOUND_MESSAGE)
    target_start = func.ST_StartPoint(target_route.geom_remainder)
    target_finish = func.ST_EndPoint(target_route.geom_remainder)
    candidate_start = func.ST_StartPoint(Route.geom)
    candidate_finish = func.ST_EndPoint(Route.geom)
    pickup_point = func.ST_LineLocatePoint(target_route.geom_remainder, candidate_start)
    dropoff_point = func.ST_LineLocatePoint(target_route.geom_remainder, candidate_finish)
    route_to_target = func.ST_ShortestLine(target_route.geom_remainder, candidate_start)
    route_from_target = func.ST_ShortestLine(target_route.geom_remainder, candidate_finish)
    common_part = func.ST_LineSubstring(target_route.geom_remainder, pickup_point, dropoff_point)
    candidate_routes = Route.query.filter(
        Route.id.in_(request.json['candidate_route_ids']),
        Route.user_id != target_route.user_id,
        func.ST_Distance(candidate_start, target_route.geom_remainder) < app.config['CANDIDATE_DISTANCE_LIMIT'],
        func.ST_Distance(candidate_finish, target_route.geom_remainder) < app.config['CANDIDATE_DISTANCE_LIMIT'],
        func.ST_Distance(candidate_finish, target_finish) < func.ST_Distance(candidate_start, target_finish)
    )
    if target_route.profile == 'foot-walking':
        candidate_routes = candidate_routes.filter(Route.trip_id != None)
    else:
        candidate_routes = candidate_routes.filter(
            # Filter out passengers left behind
            func.ST_LineLocatePoint(target_route.geom_remainder, candidate_start) > 0,
            # Passenger's overall walk must be < their ride
            func.ST_Length(common_part) >
            (func.ST_Length(route_to_target) + func.ST_Length(route_from_target))
            * 1.5,  # actual route / straight line coefficient
        )
    # Define attributes & weights for sorting: (candidate_route, target_route, weight)
    sortings = {
        'driving-car': (
            (candidate_start, target_start, .35),
            (candidate_finish, target_finish, .35),
            (candidate_start, target_route.geom_remainder, .15),
            (candidate_finish, target_route.geom_remainder, .15)
        ),
        'foot-walking': (
            (candidate_start, target_start, .35),
            (candidate_finish, target_finish, .35),
            (Route.geom_remainder, target_start, .15),
            (Route.geom_remainder, target_finish, .15)
        )
    }
    candidate_routes.order_by(sum([
        func.ST_Distance(from_, to) * weight
        for from_, to, weight in sortings[target_route.profile]
    ]))
    return [route.id for route in candidate_routes]


def geocode(text, position=MOSCOW_CENTER):
    try:
        if app.config['GEO_ENGINE'] == 'rumap':
            try:
                result = rumap.geocode(text, 'search', count=1, focus=parse_lat_lon(position))[0]
            except HTTPError:  # rumap license expired or out of quota
                app.config['GEO_ENGINE'] = 'ors'
                geocode(text)
        else:
            result = ors.geocode(text, parse_lat_lon(position))
        return Feature(result['id'], result['geometry'], result['properties'])
    except IndexError:
        abort(404, 'Nothing found; try a different text')


def suggest(text, position=MOSCOW_CENTER):
    if app.config['GEO_ENGINE'] == 'rumap':
        try:
            result = rumap.geocode(text, 'suggest', count=5, focus=parse_lat_lon(position))
        except HTTPError:  # rumap license expired or out of quota
            app.config['GEO_ENGINE'] = 'ors'
            suggest(text)
            return
    else:
        result = ors.suggest(text, parse_lat_lon(position))
    if result:
        return FeatureCollection([
            Feature(f['id'], f['geometry'], f['properties']) for f in result
        ])
    else:
        abort(404, 'Nothing found; try a different text')


def reverse_geocode(position, focus=MOSCOW_CENTER):
    routing_engine = globals()[app.config['GEO_ENGINE']]
    try:
        return routing_engine.reverse_geocode(
            parse_lat_lon(position),
            focus=parse_lat_lon(focus)
        )
    except IndexError:
        abort(404, 'Nothing found')
    except HTTPError:  # rumap license expired or out of quota
        if app.config['GEO_ENGINE'] == 'rumap':  # switch to ORS
            app.config['GEO_ENGINE'] = 'ors'
            reverse_geocode(position)
