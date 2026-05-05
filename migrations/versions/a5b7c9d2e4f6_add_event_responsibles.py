"""Add event responsibles

Revision ID: a5b7c9d2e4f6
Revises: c2f9e6a1b4d3
Create Date: 2026-05-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5b7c9d2e4f6'
down_revision = 'c2f9e6a1b4d3'
branch_labels = None
depends_on = None


def _raise_for_events_without_owner(event_ids):
    if event_ids:
        raise RuntimeError(
            'Cannot migrate event_responsibles: events without owner_username found: '
            f'{event_ids}'
        )


def upgrade():
    op.create_table(
        'event_responsibles',
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_username', sa.String(length=50), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.ForeignKeyConstraint(['user_username'], ['users.username']),
        sa.PrimaryKeyConstraint('event_id', 'user_username'),
    )
    op.create_index('ix_event_responsibles_event_id', 'event_responsibles', ['event_id'], unique=False)
    op.create_index('ix_event_responsibles_user_username', 'event_responsibles', ['user_username'], unique=False)
    op.create_index(
        'uq_event_responsibles_single_primary',
        'event_responsibles',
        ['event_id'],
        unique=True,
        sqlite_where=sa.text('is_primary = 1'),
        postgresql_where=sa.text('is_primary = true'),
    )

    bind = op.get_bind()
    metadata = sa.MetaData()

    events = sa.Table('events', metadata, autoload_with=bind)
    users = sa.Table('users', metadata, autoload_with=bind)
    event_responsibles = sa.Table('event_responsibles', metadata, autoload_with=bind)

    events_without_owner = bind.execute(
        sa.select(events.c.id).where(events.c.owner_username.is_(None))
    ).scalars().all()
    _raise_for_events_without_owner(events_without_owner)

    missing_owner_rows = bind.execute(
        sa.select(events.c.id, events.c.owner_username)
        .select_from(
            events.outerjoin(users, events.c.owner_username == users.c.username)
        )
        .where(users.c.username.is_(None))
    ).mappings().all()
    if missing_owner_rows:
        raise RuntimeError(
            'Cannot migrate event_responsibles: events reference missing users: '
            f'{[(row["id"], row["owner_username"]) for row in missing_owner_rows]}'
        )

    legacy_owner_rows = bind.execute(
        sa.select(events.c.id, events.c.owner_username)
    ).mappings().all()
    if legacy_owner_rows:
        bind.execute(
            sa.insert(event_responsibles),
            [
                {
                    'event_id': row['id'],
                    'user_username': row['owner_username'],
                    'is_primary': True,
                }
                for row in legacy_owner_rows
            ],
        )

    with op.batch_alter_table('event_responsibles', schema=None) as batch_op:
        batch_op.alter_column(
            'is_primary',
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=None,
        )


def downgrade():
    op.drop_index('uq_event_responsibles_single_primary', table_name='event_responsibles')
    op.drop_index('ix_event_responsibles_user_username', table_name='event_responsibles')
    op.drop_index('ix_event_responsibles_event_id', table_name='event_responsibles')
    op.drop_table('event_responsibles')