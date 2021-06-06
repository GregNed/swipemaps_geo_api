from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography

from api import db


class Start(db.Model):
    """"""
    user_id = db.Column(UUID(as_uuid=True), primary_key=True)
    geom = db.Column(Geography('Point', srid=4326, from_text='ST_GeomFromGeoJSON'))

    def __repr__(self):
        return f'<User {self.user_id} start>'


class Finish(db.Model):
    """"""
    user_id = db.Column(UUID(as_uuid=True), primary_key=True)
    geom = db.Column(Geography('Point', srid=4326, from_text='ST_GeomFromGeoJSON'))

    def __repr__(self):
        return f'<User {self.user_id} finish>'


class Route(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), nullable=False)
    geom = db.Column(Geography('LineString', srid=4326, from_text='ST_GeomFromGeoJSON'))

    def __repr__(self):
        return f'<User {self.user_id} route>'
