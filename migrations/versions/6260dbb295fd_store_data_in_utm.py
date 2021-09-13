"""Store data in UTM

Revision ID: 6260dbb295fd
Revises: a145a0afbcc0
Create Date: 2021-09-13 11:54:55.056629

"""
import geoalchemy2
import sqlalchemy as sa
from alembic import op


revision = '6260dbb295fd'
down_revision = 'a145a0afbcc0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('dropoff_point', sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POINT', srid=32637, from_text='ST_GeomFromEWKT', name='geometry'), nullable=False))
    op.drop_index('idx_dropoff_point_geog', table_name='dropoff_point')
    op.drop_column('dropoff_point', 'geog')
    op.add_column('pickup_point', sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POINT', srid=32637, from_text='ST_GeomFromEWKT', name='geometry'), nullable=False))
    op.drop_index('idx_pickup_point_geog', table_name='pickup_point')
    op.drop_column('pickup_point', 'geog')
    op.add_column('route', sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='LINESTRING', srid=32637, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True))
    op.drop_index('idx_route_geog', table_name='route')
    op.drop_column('route', 'geog')


def downgrade():
    op.add_column('route', sa.Column('geog', geoalchemy2.types.Geography(geometry_type='LINESTRING', srid=4326, from_text='ST_GeogFromText', name='geography'), autoincrement=False, nullable=True))
    op.create_index('idx_route_geog', 'route', ['geog'], unique=False)
    op.drop_column('route', 'geom')
    op.add_column('pickup_point', sa.Column('geog', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, from_text='ST_GeogFromText', name='geography'), autoincrement=False, nullable=False))
    op.create_index('idx_pickup_point_geog', 'pickup_point', ['geog'], unique=False)
    op.drop_column('pickup_point', 'geom')
    op.add_column('dropoff_point', sa.Column('geog', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, from_text='ST_GeogFromText', name='geography'), autoincrement=False, nullable=False))
    op.create_index('idx_dropoff_point_geog', 'dropoff_point', ['geog'], unique=False)
    op.drop_column('dropoff_point', 'geom')
