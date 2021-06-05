from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry

from api import db


class StartPoint(db.Model):
    __tablename__ = 'start_points'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=False), nullable=False)
    point = db.Column(Geometry('POINT'))

    def __init__(self, id, user_id, point):
        self.id = id
        self.user_id = user_id
        self.point = point

    def __repr__(self):
        return f'<Point {self.id}>'
