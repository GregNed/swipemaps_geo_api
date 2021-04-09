import json
from api import functions
from django.http import HttpResponse


def parse_coords(latlon):
    lat, lon = (float(x) for x in latlon.split(','))
    return [lon, lat]


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
    res = functions.route(start, end)
    return HttpResponse(json.dumps(res))
