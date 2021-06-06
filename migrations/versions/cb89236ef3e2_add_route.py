"""Add Route

Revision ID: cb89236ef3e2
Revises: 
Create Date: 2021-06-06 18:32:08.965411

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'cb89236ef3e2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('route',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('trip_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('route', geoalchemy2.types.Geography(geometry_type='LINESTRING', srid=4326, from_text='ST_GeomFromGeoJSON', name='geography'), nullable=True),
    sa.Column('start', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, from_text='ST_GeomFromGeoJSON', name='geography'), nullable=False),
    sa.Column('finish', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, from_text='ST_GeomFromGeoJSON', name='geography'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('route')
    # ### end Alembic commands ###
