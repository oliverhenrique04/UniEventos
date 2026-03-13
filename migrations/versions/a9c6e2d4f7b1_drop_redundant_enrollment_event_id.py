"""Drop redundant enrollment event_id

Revision ID: a9c6e2d4f7b1
Revises: f4b2a6c9d1e8
Create Date: 2026-03-13 00:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9c6e2d4f7b1'
down_revision = 'f4b2a6c9d1e8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('activity_enrollments', schema=None) as batch_op:
        batch_op.drop_column('event_id')


def downgrade():
    with op.batch_alter_table('activity_enrollments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('event_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_activity_enrollments_event_id_events', 'events', ['event_id'], ['id'])
