"""Enforce unique enrollment per activity and user

Revision ID: d2e4f6a8b901
Revises: c9d4b7e8f120
Create Date: 2026-03-13 03:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2e4f6a8b901'
down_revision = 'c9d4b7e8f120'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()

    enrollments = sa.Table('activity_enrollments', metadata, autoload_with=bind)

    duplicate_groups = bind.execute(
        sa.select(
            enrollments.c.activity_id,
            enrollments.c.user_cpf,
            sa.func.count(enrollments.c.id).label('cnt'),
        )
        .where(enrollments.c.user_cpf.is_not(None))
        .group_by(enrollments.c.activity_id, enrollments.c.user_cpf)
        .having(sa.func.count(enrollments.c.id) > 1)
    ).fetchall()

    for group in duplicate_groups:
        rows = bind.execute(
            sa.select(enrollments)
            .where(enrollments.c.activity_id == group.activity_id)
            .where(enrollments.c.user_cpf == group.user_cpf)
            .order_by(enrollments.c.id.asc())
        ).fetchall()

        if len(rows) <= 1:
            continue

        def score(row):
            data = row._mapping
            return (
                1 if data.get('presente') else 0,
                1 if data.get('cert_hash') else 0,
                1 if data.get('cert_entregue') else 0,
                data.get('cert_data_envio').timestamp() if data.get('cert_data_envio') else 0,
                -int(data.get('id') or 0),
            )

        keeper = sorted(rows, key=score, reverse=True)[0]
        keeper_map = keeper._mapping

        merged_nome = keeper_map.get('nome')
        merged_presente = bool(keeper_map.get('presente'))
        merged_cert_hash = keeper_map.get('cert_hash')
        merged_cert_entregue = bool(keeper_map.get('cert_entregue'))
        merged_cert_data_envio = keeper_map.get('cert_data_envio')
        merged_cert_email_alternativo = keeper_map.get('cert_email_alternativo')
        merged_lat_checkin = keeper_map.get('lat_checkin')
        merged_lon_checkin = keeper_map.get('lon_checkin')

        for row in rows:
            data = row._mapping
            merged_nome = merged_nome or data.get('nome')
            merged_presente = merged_presente or bool(data.get('presente'))
            merged_cert_hash = merged_cert_hash or data.get('cert_hash')
            merged_cert_entregue = merged_cert_entregue or bool(data.get('cert_entregue'))

            dt = data.get('cert_data_envio')
            if dt and (not merged_cert_data_envio or dt > merged_cert_data_envio):
                merged_cert_data_envio = dt

            merged_cert_email_alternativo = merged_cert_email_alternativo or data.get('cert_email_alternativo')
            if merged_lat_checkin is None:
                merged_lat_checkin = data.get('lat_checkin')
            if merged_lon_checkin is None:
                merged_lon_checkin = data.get('lon_checkin')

        bind.execute(
            sa.update(enrollments)
            .where(enrollments.c.id == keeper_map['id'])
            .values(
                nome=merged_nome,
                presente=merged_presente,
                cert_hash=merged_cert_hash,
                cert_entregue=merged_cert_entregue,
                cert_data_envio=merged_cert_data_envio,
                cert_email_alternativo=merged_cert_email_alternativo,
                lat_checkin=merged_lat_checkin,
                lon_checkin=merged_lon_checkin,
            )
        )

        duplicate_ids = [row.id for row in rows if row.id != keeper_map['id']]
        if duplicate_ids:
            bind.execute(
                sa.delete(enrollments).where(enrollments.c.id.in_(duplicate_ids))
            )

    with op.batch_alter_table('activity_enrollments', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_activity_enrollment_user_activity',
            ['activity_id', 'user_cpf'],
        )


def downgrade():
    with op.batch_alter_table('activity_enrollments', schema=None) as batch_op:
        batch_op.drop_constraint('uq_activity_enrollment_user_activity', type_='unique')
