import json
import psycopg2 as pg
import openrouteservice as ors
from api import functions
from api.helpers import parse_coords
from django.http import HttpResponse


def healthcheck(request):
    return HttpResponse(json.dumps({'status': 'OK'}))


def geocode(request):
    text = request.GET.get('text')
    res = functions.geocode(text)
    return HttpResponse(json.dumps(res))


def reverse_geocode(request):
    location = parse_coords(request.GET.get('location'))
    res = functions.reverse_geocode(location)
    return HttpResponse(json.dumps(res))


def route(request):
    start = parse_coords(request.GET.get('start'))
    end = parse_coords(request.GET.get('end'))
    num_alternatives = request.GET.get('num_alternatives', 10)
    weight_factor = request.GET.get('weight_factor', 2.0)
    share_factor = request.GET.get('share_factor', 0.8)
    client = ors.Client(base_url='http://ors:8080/ors')
    res = client.directions(
        (start, end),
        instructions=False,
        alternative_routes={
            'target_count': num_alternatives,
            'weight_factor': weight_factor,
            'share_factor': share_factor
        })
    geoms = [ors.convert.decode_polyline(route['geometry']) for route in res.get('routes', [])]
    num_geoms = len(geoms)
    features = [{'type': 'Feature', 'properties': {'count': num_geoms}, 'geometry': geom} for geom in geoms]
    for i in range(num_geoms):
        features[i]['properties']['id'] = i
    result = {'type': 'FeatureCollection', 'features': features}
    return HttpResponse(json.dumps(result))


def snap_to_road(request):
    pt = parse_coords(request.GET.get('point'))
    credentials = {
        'host': 'pg',
        'port': 5432,
        'user': 'postgres',
        # 'password': '',
        'dbname': 'postgres'
    }
    with pg.connect(**credentials) as conn:
        cur = conn.cursor()
        cur.execute("""with
            pt as (select st_setsrid(st_point(%s, %s), 4326)::geography as geog), 
            road as (
                select roads.geog, st_distance(pt.geog, roads.geog) as dist 
                from roads join pt 
                on st_dwithin(roads.geog, pt.geog, 1000)
                order by dist 
                limit 1
            ) 
            select st_asgeojson(st_closestpoint(road.geog::geometry, pt.geog::geometry)) 
            from pt, road;
        """, pt)
        pt = cur.fetchone()[0]
        lon, lat = json.loads(pt)['coordinates']
    return HttpResponse(f'{lon},{lat}')
