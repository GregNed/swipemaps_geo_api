from datetime import datetime

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
    pickup_point = db.relationship('PickupPoint', backref='route', lazy=True)

    def __repr__(self):
        return f'<Route {self.user_id}>'


class PickupPoint(db.Model):
    """"""
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    route_id = db.Column(UUID(as_uuid=True), db.ForeignKey('route.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    geom = db.Column(Geography('Point', srid=4326), nullable=False)

    def __repr__(self):
        return f'<Pickup point {self.id}>'
