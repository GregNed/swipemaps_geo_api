from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography, Geometry

from app import db


class Route(db.Model):
    """"""
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), nullable=False)
    trip_id = db.Column(UUID(as_uuid=True), unique=True)
    profile = db.Column(db.Text, nullable=False)
    distance = db.Column(db.Float)
    duration = db.Column(db.Float)
    geog = db.Column(Geography('LineString', srid=4326))
    is_handled = db.Column(db.Boolean, nullable=False, default=False)
    pickup_point = db.relationship('PickupPoint', backref='route', uselist=False, lazy=True)
    dropoff_point = db.relationship('DropoffPoint', backref='route', uselist=False, lazy=True)

    def __repr__(self):
        return f'<Route {self.user_id}>'


class PickupPoint(db.Model):
    """"""
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    route_id = db.Column(UUID(as_uuid=True), db.ForeignKey('route.id', ondelete='CASCADE'), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    geog = db.Column(Geography('Point', srid=4326), nullable=False)

    def __repr__(self):
        return f'<Pickup point {self.id}>'


class DropoffPoint(db.Model):
    """"""
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    route_id = db.Column(UUID(as_uuid=True), db.ForeignKey('route.id', ondelete='CASCADE'), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    geog = db.Column(Geography('Point', srid=4326), nullable=False)

    def __repr__(self):
        return f'<Dropoff point {self.id}>'


class PublicTransportStop(db.Model):
    """"""
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    name = db.Column(db.Text)
    geom = db.Column(Geometry('Point', srid=4326), nullable=False)

    def __repr__(self):
        return f'<Stop {self.name}>'
