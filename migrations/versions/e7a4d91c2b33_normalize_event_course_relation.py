"""Normalize event course relation

Revision ID: e7a4d91c2b33
Revises: c3e71b1a9f22
Create Date: 2026-03-13 00:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7a4d91c2b33'
down_revision = 'c3e71b1a9f22'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()

    courses = sa.Table('courses', metadata, autoload_with=bind)

    events = sa.Table('events', metadata, autoload_with=bind)

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('course_id', sa.Integer(), nullable=True))

    course_rows = bind.execute(sa.select(courses.c.id, courses.c.nome)).fetchall()
    course_name_to_id = {row.nome: row.id for row in course_rows}

    event_rows = bind.execute(sa.select(events.c.id, events.c.curso)).fetchall()
    for row in event_rows:
        curso_nome = (row.curso or '').strip()
        if not curso_nome:
            continue

        course_id = None
        for existing_name, existing_id in course_name_to_id.items():
            if existing_name and existing_name.lower() == curso_nome.lower():
                course_id = existing_id
                break

        if course_id is None:
            bind.execute(sa.insert(courses).values(nome=curso_nome))
            course_id = bind.execute(
                sa.select(courses.c.id).where(courses.c.nome == curso_nome)
            ).scalar_one()
            course_name_to_id[curso_nome] = course_id

        bind.execute(
            sa.text('UPDATE events SET course_id = :course_id WHERE id = :id'),
            {'course_id': course_id, 'id': row.id},
        )

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_events_course_id', 'courses', ['course_id'], ['id'])
        batch_op.create_index('ix_events_course_id', ['course_id'], unique=False)
        batch_op.drop_column('curso')


def downgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()

    courses = sa.Table('courses', metadata, autoload_with=bind)

    events = sa.Table('events', metadata, autoload_with=bind)

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('curso', sa.String(length=100), nullable=True))

    course_rows = bind.execute(sa.select(courses.c.id, courses.c.nome)).fetchall()
    course_id_to_name = {row.id: row.nome for row in course_rows}

    event_rows = bind.execute(sa.select(events.c.id, events.c.course_id)).fetchall()
    for row in event_rows:
        curso_nome = course_id_to_name.get(row.course_id)
        bind.execute(
            sa.text('UPDATE events SET curso = :curso WHERE id = :id'),
            {'curso': curso_nome, 'id': row.id},
        )

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_index('ix_events_course_id')
        batch_op.drop_constraint('fk_events_course_id', type_='foreignkey')
        batch_op.drop_column('course_id')
