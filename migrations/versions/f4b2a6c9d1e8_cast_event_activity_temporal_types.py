"""Cast event/activity temporal fields to typed columns

Revision ID: f4b2a6c9d1e8
Revises: e7a4d91c2b33
Create Date: 2026-03-13 00:12:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4b2a6c9d1e8'
down_revision = 'e7a4d91c2b33'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.alter_column(
            'data_inicio',
            existing_type=sa.String(length=10),
            type_=sa.Date(),
            existing_nullable=True,
            postgresql_using='NULLIF(data_inicio, \'\')::date',
        )
        batch_op.alter_column(
            'hora_inicio',
            existing_type=sa.String(length=5),
            type_=sa.Time(),
            existing_nullable=True,
            postgresql_using='NULLIF(hora_inicio, \'\')::time',
        )
        batch_op.alter_column(
            'data_fim',
            existing_type=sa.String(length=10),
            type_=sa.Date(),
            existing_nullable=True,
            postgresql_using='NULLIF(data_fim, \'\')::date',
        )
        batch_op.alter_column(
            'hora_fim',
            existing_type=sa.String(length=5),
            type_=sa.Time(),
            existing_nullable=True,
            postgresql_using='NULLIF(hora_fim, \'\')::time',
        )

    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.alter_column(
            'data_atv',
            existing_type=sa.String(length=10),
            type_=sa.Date(),
            existing_nullable=True,
            postgresql_using='NULLIF(data_atv, \'\')::date',
        )
        batch_op.alter_column(
            'hora_atv',
            existing_type=sa.String(length=5),
            type_=sa.Time(),
            existing_nullable=True,
            postgresql_using='NULLIF(hora_atv, \'\')::time',
        )


def downgrade():
    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.alter_column(
            'hora_atv',
            existing_type=sa.Time(),
            type_=sa.String(length=5),
            existing_nullable=True,
            postgresql_using="to_char(hora_atv, 'HH24:MI')",
        )
        batch_op.alter_column(
            'data_atv',
            existing_type=sa.Date(),
            type_=sa.String(length=10),
            existing_nullable=True,
            postgresql_using="to_char(data_atv, 'YYYY-MM-DD')",
        )

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.alter_column(
            'hora_fim',
            existing_type=sa.Time(),
            type_=sa.String(length=5),
            existing_nullable=True,
            postgresql_using="to_char(hora_fim, 'HH24:MI')",
        )
        batch_op.alter_column(
            'data_fim',
            existing_type=sa.Date(),
            type_=sa.String(length=10),
            existing_nullable=True,
            postgresql_using="to_char(data_fim, 'YYYY-MM-DD')",
        )
        batch_op.alter_column(
            'hora_inicio',
            existing_type=sa.Time(),
            type_=sa.String(length=5),
            existing_nullable=True,
            postgresql_using="to_char(hora_inicio, 'HH24:MI')",
        )
        batch_op.alter_column(
            'data_inicio',
            existing_type=sa.Date(),
            type_=sa.String(length=10),
            existing_nullable=True,
            postgresql_using="to_char(data_inicio, 'YYYY-MM-DD')",
        )
