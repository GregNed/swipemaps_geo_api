import json
import openrouteservice as ors
from api import functions
from api.helpers import parse_coords
from django.http import HttpResponse


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
    num_alternatives = request.GET.get('num_alternatives')
    client = ors.Client(base_url='http://localhost:8080/ors')
    routes = client.directions((start, end)).get('routes')
    res = [ors.convert.decode_polyline(geometry) for geometry in routes]
    # res = functions.route(start, end, num_alternatives=num_alternatives)
    return HttpResponse(json.dumps(res))
