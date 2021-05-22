

def parse_positions(latlon_string):
    """"""
    positions_latlon = [position.split(',') for position in latlon_string.split(';')]
    return [[float(position[1]), float(position[0])] for position in positions_latlon]
