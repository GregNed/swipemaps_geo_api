from api.views import geocode, reverse_geocode, route, healthcheck, snap_to_road
from django.urls import path


urlpatterns = [
    path('health/', healthcheck, name='healthcheck'),
    path('geocode/', geocode, name='geocode'),
    path('reverse/', reverse_geocode, name='reverse_geocode'),
    path('directions/', route, name='directions'),
    path('snap/', snap_to_road, name='snap'),
]
