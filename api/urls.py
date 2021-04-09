from api.views import geocode, reverse_geocode, route
from django.urls import path


urlpatterns = [
    path('geocode/', geocode, name='geocode'),
    path('reverse/', reverse_geocode, name='reverse_geocode'),
    path('directions/', route, name='directions'),
]
