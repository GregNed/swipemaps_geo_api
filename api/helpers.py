def parse_coords(latlon):
    lat, lon = (float(x) for x in latlon.split(','))
    return [lon, lat]
