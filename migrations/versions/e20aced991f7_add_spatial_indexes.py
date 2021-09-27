"""Add spatial indexes

Revision ID: e20aced991f7
Revises: b78044fe6891
Create Date: 2021-09-27 20:34:51.108710

"""
from alembic import op


revision = 'e20aced991f7'
down_revision = 'b78044fe6891'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('idx_route_geom', 'route', ['geom'], postgresql_using='gist')
    op.create_index('idx_pickup_point_geom', 'pickup_point', ['geom'], postgresql_using='gist')
    op.create_index('idx_dropoff_point_geom', 'dropoff_point', ['geom'], postgresql_using='gist')


def downgrade():
    op.drop_index('idx_route_geom', 'route')
    op.drop_index('idx_pickup_point_geom', 'pickup_point')
    op.drop_index('idx_dropoff_point_geom', 'dropoff_point')
