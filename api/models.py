from sqlalchemy import Column, Float
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography

from api import db


class Route(db.Model):
    """"""
    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    trip_id = Column(UUID(as_uuid=True), unique=True)
    route = Column(Geography('LineString', srid=4326, from_text='ST_GeomFromGeoJSON'))
    start = Column(Geography('Point', srid=4326, from_text='ST_GeomFromGeoJSON'), nullable=False)
    finish = Column(Geography('Point', srid=4326, from_text='ST_GeomFromGeoJSON'), nullable=False)
    distance = Column(Float)
    duration = Column(Float)

    def __repr__(self):
        return f'<User {self.user_id} route>'
