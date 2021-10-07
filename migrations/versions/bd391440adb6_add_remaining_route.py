"""
Message: Add remaining route
Revision ID: bd391440adb6
Revises: d58a6d99cebc
Create Date: 2021-10-06 16:59:46.318048
"""
import geoalchemy2
import sqlalchemy as sa
from alembic import op


revision = 'bd391440adb6'
down_revision = 'd58a6d99cebc'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('route', sa.Column('geom_remainder',
                                     geoalchemy2.types.Geometry(geometry_type='LINESTRING', srid=32637, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True
                                     ))
    op.create_index('idx_route_geom_remainder', 'route', ['geom_remainder'], unique=False, postgresql_using='gist')


def downgrade():
    op.drop_index('idx_route_geom_remainder', table_name='route', postgresql_using='gist')
    op.drop_column('route', 'geom_remainder')
