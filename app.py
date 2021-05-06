import functions
import json
import psycopg2 as pg
import openrouteservice as ors
from flask import Flask, request
from helpers import parse_coords


app = Flask(__name__)


@app.route('/', methods=['GET'])
def healthcheck():
    return json.dumps({'status': 'OK'})


@app.route('/geocode/', methods=['GET'])
def geocode():
    text = request.args.get('text')
    result = functions.geocode(text)
    return json.dumps(result)


@app.route('/reverse/', methods=['GET'])
def reverse_geocode():
    location = parse_coords(request.args.get('point'))
    result = functions.reverse_geocode(location)
    return json.dumps(result)


@app.route('/directions/', methods=['GET'])
def directions():
    start = parse_coords(request.args.get('start'))
    end = parse_coords(request.args.get('end'))
    num_alternatives = request.args.get('num_alternatives', 10)
    weight_factor = request.args.get('weight_factor', 2.0)
    share_factor = request.args.get('share_factor', 0.8)
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
    return json.dumps({'type': 'FeatureCollection', 'features': features})


@app.route('/snap/', methods=['GET'])
def snap_to_road():
    pt = parse_coords(request.args.get('point'))
    with pg.connect("host=pg user=postgres") as conn:
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
    return f'{lon},{lat}'


if __name__ == '__main__':
    app.run()
