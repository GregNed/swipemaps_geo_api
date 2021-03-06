"""PickupPoint: make route_id unique

Revision ID: 044446c8c4e5
Revises: 00ce4fb4831a
Create Date: 2021-08-16 14:19:03.082698

"""
import geoalchemy2
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = '044446c8c4e5'
down_revision = '00ce4fb4831a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(None, 'pickup_point', ['route_id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'pickup_point', type_='unique')
    # ### end Alembic commands ###
