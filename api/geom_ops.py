from shapely.geometry import shape


def get_midpoint(linestring_geom):
    """"""
    ls = shape(linestring_geom)
    midpoint = ls.interpolate(0.5, normalized=True)
    return midpoint.coords[0]  # first position (out of 1), not lon
