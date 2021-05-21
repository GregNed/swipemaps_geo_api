import json
import psycopg2 as pg


conn_info = {
    'host': 'pg',
    'user': 'postgres',
    'password': 'postgres'
}


def snap_to_road(position):
    """Find the closest point on the closest road

    Accepts a position, returns a Point object.
    """
    try:
        conn = pg.connect(**conn_info)
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
            """, position)
        return json.loads(next(cur)[0])['coordinates']
    except (StopIteration, pg.ProgrammingError):
        # if no results (most likely bc point is too far from roads)
        return position
    finally:
        conn.close()
        cur.close()
