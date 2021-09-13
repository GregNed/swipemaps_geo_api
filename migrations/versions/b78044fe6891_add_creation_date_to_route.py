"""Add creation date to Route

Revision ID: b78044fe6891
Revises: 6260dbb295fd
Create Date: 2021-09-13 13:47:49.973420

"""
import geoalchemy2
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b78044fe6891'
down_revision = '6260dbb295fd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('route', sa.Column('created_at', sa.DateTime(), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('route', 'created_at')
    # ### end Alembic commands ###