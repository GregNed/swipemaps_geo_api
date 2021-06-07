from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography

from api import db


class Route(db.Model):
    """"""
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), nullable=False)
    trip_id = db.Column(UUID(as_uuid=True))
    route = db.Column(Geography('LineString', srid=4326, from_text='ST_GeomFromGeoJSON'))
    start = db.Column(Geography('Point', srid=4326, from_text='ST_GeomFromGeoJSON'), nullable=False)
    finish = db.Column(Geography('Point', srid=4326, from_text='ST_GeomFromGeoJSON'), nullable=False)

    def __repr__(self):
        return f'<User {self.user_id} route>'
