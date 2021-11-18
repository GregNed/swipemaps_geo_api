from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry

from app import db


class Route(db.Model):
    """"""
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), nullable=False)
    trip_id = db.Column(UUID(as_uuid=True), unique=True)
    profile = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    distance = db.Column(db.Float)
    duration = db.Column(db.Float)
    geom = db.Column(Geometry('LineString', srid=32637, spatial_index=False))
    geom_remainder = db.Column(Geometry('LineString', srid=32637, spatial_index=False))
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
    geom = db.Column(Geometry('Point', srid=32637, spatial_index=False), nullable=False)

    def __repr__(self):
        return f'<Pickup point {self.id}>'


class DropoffPoint(db.Model):
    """"""
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    route_id = db.Column(UUID(as_uuid=True), db.ForeignKey('route.id', ondelete='CASCADE'), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    geom = db.Column(Geometry('Point', srid=32637, spatial_index=False), nullable=False)

    def __repr__(self):
        return f'<Dropoff point {self.id}>'


class PublicTransportStop(db.Model):
    """"""
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    name = db.Column(db.Text)
    geom = db.Column(Geometry('Point', srid=32637, spatial_index=False), nullable=False)

    def __repr__(self):
        return f'<Stop {self.name}>'


class Aoi(db.Model):
    """"""
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    name = db.Column(db.Text)
    geom = db.Column(Geometry('Polygon', srid=3857, spatial_index=False), nullable=False)

    def __repr__(self):
        return f'<Area {self.name}>'


class Road(db.Model):
    """"""
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    name = db.Column(db.Text)
    type = db.Column(db.Text)
    geom = db.Column(Geometry('LineString', srid=32637, spatial_index=False), nullable=False)

    def __repr__(self):
        return f'<Road {self.name}>'


# Create spatial indexes explicitly since alembic dropoff those implied by GeoAlchemy
db.Index('idx_route_geom', Route.geom, postgresql_using='gist')
db.Index('idx_route_geom_remainder', Route.geom_remainder, postgresql_using='gist')
db.Index('idx_pickup_point_geom', PickupPoint.geom, postgresql_using='gist')
db.Index('idx_dropoff_point_geom', DropoffPoint.geom, postgresql_using='gist')
db.Index('idx_public_transport_stop_geom', PublicTransportStop.geom, postgresql_using='gist')
db.Index('idx_aoi_geom', Aoi.geom, postgresql_using='gist')
db.Index('idx_road_geom', Road.geom, postgresql_using='gist')
