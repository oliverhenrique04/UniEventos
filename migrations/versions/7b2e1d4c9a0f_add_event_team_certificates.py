"""Add event team certificates

Revision ID: 7b2e1d4c9a0f
Revises: a5b7c9d2e4f6
Create Date: 2026-06-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b2e1d4c9a0f'
down_revision = 'a5b7c9d2e4f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cert_team_bg_path', sa.String(length=200), nullable=True, server_default='file/fundo_padrao.png'))
        batch_op.add_column(sa.Column('cert_team_template_json', sa.Text(), nullable=True))

    op.create_table(
        'event_team_certificate_recipients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=True),
        sa.Column('nome', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('cpf', sa.String(length=11), nullable=True),
        sa.Column('role_label', sa.String(length=80), nullable=False),
        sa.Column('workload_hours', sa.String(length=20), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False, default='manual'),
        sa.Column('source_key', sa.String(length=160), nullable=True),
        sa.Column('cert_hash', sa.String(length=16), nullable=True, unique=True),
        sa.Column('cert_entregue', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('cert_data_envio', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint(
            "source in ('automatico', 'manual')",
            name='ck_event_team_cert_recipient_source',
        ),
        sa.UniqueConstraint(
            'event_id', 'source', 'source_key',
            name='uq_event_team_cert_recipient_source_key',
        ),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_event_team_cert_recipient_event_id', 'event_team_certificate_recipients', ['event_id'], unique=False)
    op.create_index('ix_event_team_cert_recipient_activity_id', 'event_team_certificate_recipients', ['activity_id'], unique=False)
    op.create_index('ix_event_team_cert_recipient_entregue', 'event_team_certificate_recipients', ['cert_entregue'], unique=False)
    op.create_index('ix_event_team_cert_recipient_source', 'event_team_certificate_recipients', ['source'], unique=False)


def downgrade():
    op.drop_index('ix_event_team_cert_recipient_source', table_name='event_team_certificate_recipients')
    op.drop_index('ix_event_team_cert_recipient_entregue', table_name='event_team_certificate_recipients')
    op.drop_index('ix_event_team_cert_recipient_activity_id', table_name='event_team_certificate_recipients')
    op.drop_index('ix_event_team_cert_recipient_event_id', table_name='event_team_certificate_recipients')
    op.drop_table('event_team_certificate_recipients')

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_column('cert_team_template_json')
        batch_op.drop_column('cert_team_bg_path')
