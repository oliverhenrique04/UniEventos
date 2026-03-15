"""Add speaker email to activities

Revision ID: f2c4d8b1a7e3
Revises: e1a7c5b93d21
Create Date: 2026-03-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2c4d8b1a7e3'
down_revision = 'e1a7c5b93d21'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_palestrante', sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.drop_column('email_palestrante')
