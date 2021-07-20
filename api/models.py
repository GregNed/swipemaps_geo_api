from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography

from api import db


class Route(db.Model):
    """"""
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), nullable=False)
    trip_id = db.Column(UUID(as_uuid=True), unique=True)
    profile = db.Column(db.Text, nullable=False)
    route = db.Column(Geography('LineString', srid=4326))
    start = db.Column(Geography('Point', srid=4326), nullable=False)
    finish = db.Column(Geography('Point', srid=4326), nullable=False)
    distance = db.Column(db.Float)
    duration = db.Column(db.Float)

    def __repr__(self):
        return f'<User {self.user_id} route>'
