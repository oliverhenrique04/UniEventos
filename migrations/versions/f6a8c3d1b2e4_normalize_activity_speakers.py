"""Normalize activity speakers

Revision ID: f6a8c3d1b2e4
Revises: f2c4d8b1a7e3
Create Date: 2026-03-15 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a8c3d1b2e4'
down_revision = 'f2c4d8b1a7e3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'activity_speakers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('ordem', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_activity_speakers_activity_id', 'activity_speakers', ['activity_id'], unique=False)
    op.create_index('ix_activity_speakers_ordem', 'activity_speakers', ['ordem'], unique=False)

    bind = op.get_bind()
    metadata = sa.MetaData()
    activities = sa.Table(
        'activities',
        metadata,
        sa.Column('id', sa.Integer()),
        sa.Column('palestrante', sa.String(length=100)),
        sa.Column('email_palestrante', sa.String(length=120)),
    )
    activity_speakers = sa.Table(
        'activity_speakers',
        metadata,
        sa.Column('activity_id', sa.Integer()),
        sa.Column('nome', sa.String(length=100)),
        sa.Column('email', sa.String(length=120)),
        sa.Column('ordem', sa.Integer()),
    )

    rows = bind.execute(
        sa.select(
            activities.c.id,
            activities.c.palestrante,
            activities.c.email_palestrante,
        )
    ).mappings().all()

    speaker_rows = []
    for row in rows:
        speaker_name = str(row.get('palestrante') or '').strip() or None
        speaker_email = str(row.get('email_palestrante') or '').strip() or None
        if not speaker_name and not speaker_email:
            continue
        speaker_rows.append({
            'activity_id': row['id'],
            'nome': speaker_name,
            'email': speaker_email,
            'ordem': 0,
        })

    if speaker_rows:
        op.bulk_insert(activity_speakers, speaker_rows)

    with op.batch_alter_table('activity_speakers', schema=None) as batch_op:
        batch_op.alter_column('ordem', server_default=None)


def downgrade():
    op.drop_index('ix_activity_speakers_ordem', table_name='activity_speakers')
    op.drop_index('ix_activity_speakers_activity_id', table_name='activity_speakers')
    op.drop_table('activity_speakers')
