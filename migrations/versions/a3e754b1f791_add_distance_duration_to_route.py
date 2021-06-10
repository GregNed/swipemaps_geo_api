"""Add distance & duration to Route

Revision ID: a3e754b1f791
Revises: 08ef7a2da591
Create Date: 2021-06-10 11:41:32.780687

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision = 'a3e754b1f791'
down_revision = '08ef7a2da591'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('route', sa.Column('distance', sa.Float(), nullable=True))
    op.add_column('route', sa.Column('duration', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('route', 'duration')
    op.drop_column('route', 'distance')
    # ### end Alembic commands ###
