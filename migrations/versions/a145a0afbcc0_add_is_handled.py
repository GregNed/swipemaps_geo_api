"""Add is_handled

Revision ID: a145a0afbcc0
Revises: 0c4e6ebd4845
Create Date: 2021-09-09 18:13:11.377315

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a145a0afbcc0'
down_revision = '0c4e6ebd4845'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('route', sa.Column('is_handled', sa.Boolean(), nullable=False))


def downgrade():
    op.drop_column('route', 'is_handled')
