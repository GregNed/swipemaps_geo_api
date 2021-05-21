from shapely.geometry import LineString


def get_midpoint(coords):
    """"""
    ls = LineString(coords)
    midpoint = ls.interpolate(0.5, normalized=True)
    return midpoint.coords[0]  # first position (out of 1), not lon
