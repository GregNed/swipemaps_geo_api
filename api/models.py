from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry

from api import db


class Location(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), nullable=False)
    kind = db.Column(db.String, nullable=False)
    geom = db.Column(Geometry('POINT', srid=4326, from_text='ST_GeomFromGeoJSON'))

    def __repr__(self):
        return f'<User {self.user_id} {self.kind} point>'


class Route(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), nullable=False)
    geom = db.Column(Geometry('LineString', srid=4326, from_text='ST_GeomFromGeoJSON'))

    def __repr__(self):
        return f'<User {self.user_id} route>'
