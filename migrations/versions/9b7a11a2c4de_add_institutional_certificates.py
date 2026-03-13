"""Add institutional certificates

Revision ID: 9b7a11a2c4de
Revises: f813342fad29
Create Date: 2026-03-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b7a11a2c4de'
down_revision = 'f813342fad29'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'institutional_certificates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_by_username', sa.String(length=50), nullable=False),
        sa.Column('titulo', sa.String(length=140), nullable=False),
        sa.Column('categoria', sa.String(length=80), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('data_emissao', sa.String(length=10), nullable=False),
        sa.Column('signer_name', sa.String(length=120), nullable=True),
        sa.Column('cert_bg_path', sa.String(length=200), nullable=True),
        sa.Column('cert_template_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_username'], ['users.username']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'institutional_certificate_recipients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('certificate_id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('cpf', sa.String(length=14), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('cert_hash', sa.String(length=16), nullable=True),
        sa.Column('cert_entregue', sa.Boolean(), nullable=True),
        sa.Column('cert_data_envio', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['certificate_id'], ['institutional_certificates.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('certificate_id', 'email', name='uq_institutional_recipient_email_per_cert'),
        sa.UniqueConstraint('cert_hash')
    )


def downgrade():
    op.drop_table('institutional_certificate_recipients')
    op.drop_table('institutional_certificates')
