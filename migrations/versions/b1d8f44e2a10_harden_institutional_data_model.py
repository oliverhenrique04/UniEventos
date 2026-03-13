"""Harden institutional data model

Revision ID: b1d8f44e2a10
Revises: 9b7a11a2c4de
Create Date: 2026-03-12 23:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1d8f44e2a10'
down_revision = '9b7a11a2c4de'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('institutional_certificates', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'ck_institutional_certificate_status',
            "status in ('RASCUNHO', 'ENVIADO', 'ARQUIVADO')"
        )
        batch_op.create_index('ix_institutional_cert_created_by', ['created_by_username'], unique=False)
        batch_op.create_index('ix_institutional_cert_status', ['status'], unique=False)
        batch_op.create_index('ix_institutional_cert_categoria', ['categoria'], unique=False)

    with op.batch_alter_table('institutional_certificate_recipients', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_institutional_recipient_cpf_per_cert',
            ['certificate_id', 'cpf']
        )
        batch_op.create_index('ix_institutional_recipient_certificate_id', ['certificate_id'], unique=False)
        batch_op.create_index('ix_institutional_recipient_entregue', ['cert_entregue'], unique=False)
        batch_op.create_index('ix_institutional_recipient_data_envio', ['cert_data_envio'], unique=False)


def downgrade():
    with op.batch_alter_table('institutional_certificate_recipients', schema=None) as batch_op:
        batch_op.drop_index('ix_institutional_recipient_data_envio')
        batch_op.drop_index('ix_institutional_recipient_entregue')
        batch_op.drop_index('ix_institutional_recipient_certificate_id')
        batch_op.drop_constraint('uq_institutional_recipient_cpf_per_cert', type_='unique')

    with op.batch_alter_table('institutional_certificates', schema=None) as batch_op:
        batch_op.drop_index('ix_institutional_cert_categoria')
        batch_op.drop_index('ix_institutional_cert_status')
        batch_op.drop_index('ix_institutional_cert_created_by')
        batch_op.drop_constraint('ck_institutional_certificate_status', type_='check')
