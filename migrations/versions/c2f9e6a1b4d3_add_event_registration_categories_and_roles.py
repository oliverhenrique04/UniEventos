"""Add event registration categories and allowed roles

Revision ID: c2f9e6a1b4d3
Revises: f6a8c3d1b2e4
Create Date: 2026-03-16 20:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2f9e6a1b4d3'
down_revision = 'f6a8c3d1b2e4'
branch_labels = None
depends_on = None


DEFAULT_ROLES = ('participante', 'professor', 'coordenador', 'gestor')
DEFAULT_CATEGORY_NAME = 'Geral'


def upgrade():
    op.create_table(
        'event_allowed_roles',
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.PrimaryKeyConstraint('event_id', 'role'),
        sa.CheckConstraint(
            "role in ('participante', 'professor', 'coordenador', 'gestor')",
            name='ck_event_allowed_role_value',
        ),
    )
    op.create_index(
        'ix_event_allowed_roles_role',
        'event_allowed_roles',
        ['role'],
        unique=False,
    )

    op.create_table(
        'event_registration_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=80), nullable=False),
        sa.Column('vagas', sa.Integer(), nullable=False, server_default='-1'),
        sa.Column('ordem', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'nome', name='uq_event_registration_category_event_name'),
    )
    op.create_index(
        'ix_event_registration_categories_event_id',
        'event_registration_categories',
        ['event_id'],
        unique=False,
    )
    op.create_index(
        'ix_event_registration_categories_ordem',
        'event_registration_categories',
        ['ordem'],
        unique=False,
    )

    op.create_table(
        'event_registrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_cpf', sa.String(length=11), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['event_registration_categories.id']),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.ForeignKeyConstraint(['user_cpf'], ['users.cpf']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'user_cpf', name='uq_event_registration_event_user'),
    )
    op.create_index('ix_event_registrations_event_id', 'event_registrations', ['event_id'], unique=False)
    op.create_index('ix_event_registrations_user_cpf', 'event_registrations', ['user_cpf'], unique=False)
    op.create_index('ix_event_registrations_category_id', 'event_registrations', ['category_id'], unique=False)

    with op.batch_alter_table('activity_enrollments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('event_registration_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            'ix_activity_enrollments_event_registration_id',
            ['event_registration_id'],
            unique=False,
        )
        batch_op.create_foreign_key(
            'fk_activity_enrollments_event_registration_id',
            'event_registrations',
            ['event_registration_id'],
            ['id'],
        )

    bind = op.get_bind()
    metadata = sa.MetaData()

    events = sa.Table('events', metadata, autoload_with=bind)
    activities = sa.Table('activities', metadata, autoload_with=bind)
    enrollments = sa.Table('activity_enrollments', metadata, autoload_with=bind)
    allowed_roles = sa.Table('event_allowed_roles', metadata, autoload_with=bind)
    categories = sa.Table('event_registration_categories', metadata, autoload_with=bind)
    registrations = sa.Table('event_registrations', metadata, autoload_with=bind)

    event_ids = [row.id for row in bind.execute(sa.select(events.c.id)).fetchall()]
    category_ids_by_event = {}

    for event_id in event_ids:
        for role in DEFAULT_ROLES:
            bind.execute(
                sa.insert(allowed_roles).values(event_id=event_id, role=role)
            )

        result = bind.execute(
            sa.insert(categories).values(
                event_id=event_id,
                nome=DEFAULT_CATEGORY_NAME,
                vagas=-1,
                ordem=0,
            )
        )
        category_ids_by_event[event_id] = result.inserted_primary_key[0]

    event_user_pairs = bind.execute(
        sa.select(activities.c.event_id, enrollments.c.user_cpf)
        .select_from(
            enrollments.join(activities, enrollments.c.activity_id == activities.c.id)
        )
        .where(enrollments.c.user_cpf.is_not(None))
        .distinct()
    ).fetchall()

    for row in event_user_pairs:
        category_id = category_ids_by_event.get(row.event_id)
        if category_id is None:
            continue

        registration_result = bind.execute(
            sa.insert(registrations).values(
                event_id=row.event_id,
                user_cpf=row.user_cpf,
                category_id=category_id,
            )
        )
        registration_id = registration_result.inserted_primary_key[0]

        bind.execute(
            sa.text(
                """
                UPDATE activity_enrollments
                SET event_registration_id = :registration_id
                WHERE user_cpf = :user_cpf
                  AND activity_id IN (
                      SELECT id
                      FROM activities
                      WHERE event_id = :event_id
                  )
                """
            ),
            {
                'registration_id': registration_id,
                'user_cpf': row.user_cpf,
                'event_id': row.event_id,
            },
        )


def downgrade():
    with op.batch_alter_table('activity_enrollments', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_activity_enrollments_event_registration_id',
            type_='foreignkey',
        )
        batch_op.drop_index('ix_activity_enrollments_event_registration_id')
        batch_op.drop_column('event_registration_id')

    op.drop_index('ix_event_registrations_category_id', table_name='event_registrations')
    op.drop_index('ix_event_registrations_user_cpf', table_name='event_registrations')
    op.drop_index('ix_event_registrations_event_id', table_name='event_registrations')
    op.drop_table('event_registrations')

    op.drop_index(
        'ix_event_registration_categories_ordem',
        table_name='event_registration_categories',
    )
    op.drop_index(
        'ix_event_registration_categories_event_id',
        table_name='event_registration_categories',
    )
    op.drop_table('event_registration_categories')

    op.drop_index('ix_event_allowed_roles_role', table_name='event_allowed_roles')
    op.drop_table('event_allowed_roles')
