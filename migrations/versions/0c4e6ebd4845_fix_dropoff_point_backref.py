"""Fix dropoff point backref

Revision ID: 0c4e6ebd4845
Revises: 12e1cb995194
Create Date: 2021-08-26 16:01:16.571216

"""
import geoalchemy2
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = '0c4e6ebd4845'
down_revision = '12e1cb995194'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('idx_dropoff_point_geog', table_name='dropoff_point')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index('idx_dropoff_point_geog', 'dropoff_point', ['geog'], unique=False)
    # ### end Alembic commands ###
