"""Strengthen institutional recipient user reference

Revision ID: e1a7c5b93d21
Revises: d2e4f6a8b901
Create Date: 2026-03-14 21:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
import json


# revision identifiers, used by Alembic.
revision = 'e1a7c5b93d21'
down_revision = 'd2e4f6a8b901'
branch_labels = None
depends_on = None


def _safe_metadata(value):
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()

    recipients = sa.Table(
        'institutional_certificate_recipients',
        metadata,
        sa.Column('id', sa.Integer),
        sa.Column('certificate_id', sa.Integer),
        sa.Column('user_username', sa.String(length=50)),
        sa.Column('email', sa.String(length=120)),
        sa.Column('cpf', sa.String(length=14)),
        sa.Column('metadata_json', sa.Text),
    )

    users = sa.Table(
        'users',
        metadata,
        sa.Column('username', sa.String(length=50)),
        sa.Column('email', sa.String(length=120)),
        sa.Column('cpf', sa.String(length=14)),
        sa.Column('ra', sa.String(length=30)),
    )

    # Normalize recipient emails to lowercase for stable matching.
    rows = bind.execute(
        sa.select(recipients.c.id, recipients.c.email)
    ).fetchall()

    for row in rows:
        email = (row.email or '').strip().lower() or None
        if email != row.email:
            bind.execute(
                sa.update(recipients)
                .where(recipients.c.id == row.id)
                .values(email=email)
            )

    # Backfill missing user link using cpf/email/username/ra hints.
    rows = bind.execute(
        sa.select(
            recipients.c.id,
            recipients.c.user_username,
            recipients.c.cpf,
            recipients.c.email,
            recipients.c.metadata_json,
        )
    ).fetchall()

    for row in rows:
        if (row.user_username or '').strip():
            continue

        linked_username = None
        cpf = (row.cpf or '').strip()
        email = (row.email or '').strip().lower()
        metadata_map = _safe_metadata(row.metadata_json)
        username_hint = (metadata_map.get('username') or '').strip()
        ra_hint = (metadata_map.get('ra') or '').strip()

        if cpf:
            linked_username = bind.execute(
                sa.select(users.c.username).where(users.c.cpf == cpf).limit(1)
            ).scalar()

        if not linked_username and email:
            linked_username = bind.execute(
                sa.select(users.c.username).where(sa.func.lower(users.c.email) == email).limit(1)
            ).scalar()

        if not linked_username and username_hint:
            linked_username = bind.execute(
                sa.select(users.c.username).where(users.c.username == username_hint).limit(1)
            ).scalar()

        if not linked_username and ra_hint:
            linked_username = bind.execute(
                sa.select(users.c.username).where(users.c.ra == ra_hint).limit(1)
            ).scalar()

        if linked_username:
            bind.execute(
                sa.update(recipients)
                .where(recipients.c.id == row.id)
                .values(user_username=linked_username)
            )

    # Remove duplicate (certificate_id, user_username) links by keeping the oldest row.
    duplicates = bind.execute(
        sa.select(
            recipients.c.certificate_id,
            recipients.c.user_username,
            sa.func.count(recipients.c.id).label('cnt'),
        )
        .where(recipients.c.user_username.is_not(None))
        .group_by(recipients.c.certificate_id, recipients.c.user_username)
        .having(sa.func.count(recipients.c.id) > 1)
    ).fetchall()

    for group in duplicates:
        group_rows = bind.execute(
            sa.select(recipients.c.id)
            .where(recipients.c.certificate_id == group.certificate_id)
            .where(recipients.c.user_username == group.user_username)
            .order_by(recipients.c.id.asc())
        ).fetchall()

        # Keep the first row linked and detach duplicates to preserve data without deleting rows.
        for dup in group_rows[1:]:
            bind.execute(
                sa.update(recipients)
                .where(recipients.c.id == dup.id)
                .values(user_username=None)
            )

    with op.batch_alter_table('institutional_certificate_recipients', schema=None) as batch_op:
        batch_op.create_index(
            'uq_institutional_recipient_user_per_cert',
            ['certificate_id', 'user_username'],
            unique=True,
        )


def downgrade():
    with op.batch_alter_table('institutional_certificate_recipients', schema=None) as batch_op:
        batch_op.drop_index('uq_institutional_recipient_user_per_cert')
