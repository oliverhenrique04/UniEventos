"""Normalize user course relation

Revision ID: b6f1d3c8a2e4
Revises: a9c6e2d4f7b1
Create Date: 2026-03-12 23:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6f1d3c8a2e4'
down_revision = 'a9c6e2d4f7b1'
branch_labels = None
depends_on = None


def _has_column(bind, table_name, column_name):
	inspector = sa.inspect(bind)
	columns = {column['name'] for column in inspector.get_columns(table_name)}
	return column_name in columns


def upgrade():
	bind = op.get_bind()

	if not _has_column(bind, 'users', 'curso'):
		return

	users = sa.table(
		'users',
		sa.column('course_id', sa.Integer),
		sa.column('curso', sa.String),
	)
	courses = sa.table(
		'courses',
		sa.column('id', sa.Integer),
		sa.column('nome', sa.String),
	)

	# Backfill relation for rows that still only have the legacy course name.
	op.execute(
		users.update()
		.where(users.c.course_id.is_(None))
		.where(users.c.curso.is_not(None))
		.where(sa.func.length(sa.func.trim(users.c.curso)) > 0)
		.values(
			course_id=sa.select(courses.c.id)
			.where(sa.func.lower(courses.c.nome) == sa.func.lower(sa.func.trim(users.c.curso)))
			.limit(1)
			.scalar_subquery()
		)
	)

	with op.batch_alter_table('users', schema=None) as batch_op:
		batch_op.drop_column('curso')


def downgrade():
	bind = op.get_bind()

	if _has_column(bind, 'users', 'curso'):
		return

	with op.batch_alter_table('users', schema=None) as batch_op:
		batch_op.add_column(sa.Column('curso', sa.String(length=100), nullable=True))

	users = sa.table(
		'users',
		sa.column('course_id', sa.Integer),
		sa.column('curso', sa.String),
	)
	courses = sa.table(
		'courses',
		sa.column('id', sa.Integer),
		sa.column('nome', sa.String),
	)

	# Rehydrate legacy textual field for rollback compatibility.
	op.execute(
		users.update().values(
			curso=sa.select(courses.c.nome)
			.where(courses.c.id == users.c.course_id)
			.limit(1)
			.scalar_subquery()
		)
	)
