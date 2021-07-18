"""empty message

Revision ID: a29c7dcd0bc4
Revises: a3e754b1f791
Create Date: 2021-07-18 02:58:00.894255

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a29c7dcd0bc4'
down_revision = 'a3e754b1f791'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('route', sa.Column('profile', sa.Text(), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('route', 'profile')
    # ### end Alembic commands ###
