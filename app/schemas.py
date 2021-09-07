from app import ma
from app.models import Route


class RouteSchema(ma.SQLAlchemyAutoSchema):
    """"""
    class Meta:
        model = Route
        exclude = 'geog', 'pickup_point', 'dropoff_point'
