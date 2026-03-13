"""Link institutional recipient to user

Revision ID: c9d4b7e8f120
Revises: b6f1d3c8a2e4
Create Date: 2026-03-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9d4b7e8f120'
down_revision = 'b6f1d3c8a2e4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('institutional_certificate_recipients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_username', sa.String(length=50), nullable=True))

    bind = op.get_bind()
    metadata = sa.MetaData()

    recipients = sa.Table('institutional_certificate_recipients', metadata, autoload_with=bind)
    users = sa.Table('users', metadata, autoload_with=bind)

    rows = bind.execute(
        sa.select(recipients.c.id, recipients.c.cpf, recipients.c.email)
    ).fetchall()

    for row in rows:
        linked_username = None
        cpf = (row.cpf or '').strip()
        email = (row.email or '').strip().lower()

        if cpf:
            linked_username = bind.execute(
                sa.select(users.c.username).where(users.c.cpf == cpf).limit(1)
            ).scalar()

        if not linked_username and email:
            linked_username = bind.execute(
                sa.select(users.c.username).where(sa.func.lower(users.c.email) == email).limit(1)
            ).scalar()

        if linked_username:
            bind.execute(
                sa.update(recipients)
                .where(recipients.c.id == row.id)
                .values(user_username=linked_username)
            )

    with op.batch_alter_table('institutional_certificate_recipients', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_institutional_recipient_user_username',
            'users',
            ['user_username'],
            ['username'],
        )
        batch_op.create_index('ix_institutional_recipient_user_username', ['user_username'], unique=False)


def downgrade():
    with op.batch_alter_table('institutional_certificate_recipients', schema=None) as batch_op:
        batch_op.drop_index('ix_institutional_recipient_user_username')
        batch_op.drop_constraint('fk_institutional_recipient_user_username', type_='foreignkey')
        batch_op.drop_column('user_username')
