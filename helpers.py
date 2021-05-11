

def parse_position(latlon):
    lat, lon = (float(x) for x in latlon.split(','))
    return (lon, lat)
