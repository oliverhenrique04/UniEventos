"""Normalize institutional category

Revision ID: c3e71b1a9f22
Revises: b1d8f44e2a10
Create Date: 2026-03-12 23:59:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3e71b1a9f22'
down_revision = 'b1d8f44e2a10'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'institutional_certificate_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nome'),
    )

    bind = op.get_bind()
    metadata = sa.MetaData()

    certificates = sa.Table('institutional_certificates', metadata, autoload_with=bind)

    categories = sa.Table('institutional_certificate_categories', metadata, autoload_with=bind)

    with op.batch_alter_table('institutional_certificates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))

    category_name_to_id = {}

    rows = bind.execute(sa.select(certificates.c.categoria).distinct()).fetchall()
    category_names = []
    for row in rows:
        nome = (row[0] or '').strip()
        if nome:
            category_names.append(nome)

    if not category_names:
        category_names = ['Sem Categoria']

    for nome in sorted(set(category_names), key=lambda x: x.lower()):
        bind.execute(sa.insert(categories).values(nome=nome))

    category_rows = bind.execute(sa.select(categories.c.id, categories.c.nome)).fetchall()
    for row in category_rows:
        category_name_to_id[row.nome] = row.id

    default_category_id = category_name_to_id.get('Sem Categoria')
    if default_category_id is None:
        bind.execute(sa.insert(categories).values(nome='Sem Categoria'))
        default_category_id = bind.execute(
            sa.select(categories.c.id).where(categories.c.nome == 'Sem Categoria')
        ).scalar_one()

    certificate_rows = bind.execute(sa.select(certificates.c.id, certificates.c.categoria)).fetchall()
    for row in certificate_rows:
        nome = (row.categoria or '').strip()
        category_id = category_name_to_id.get(nome, default_category_id)
        bind.execute(
            sa.text('UPDATE institutional_certificates SET category_id = :category_id WHERE id = :id'),
            {'category_id': category_id, 'id': row.id},
        )

    with op.batch_alter_table('institutional_certificates', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_institutional_certificates_category_id',
            'institutional_certificate_categories',
            ['category_id'],
            ['id'],
        )
        batch_op.create_index('ix_institutional_cert_category_id', ['category_id'], unique=False)
        batch_op.drop_index('ix_institutional_cert_categoria')
        batch_op.alter_column('category_id', nullable=False)
        batch_op.drop_column('categoria')


def downgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()

    certificates = sa.Table('institutional_certificates', metadata, autoload_with=bind)

    categories = sa.Table('institutional_certificate_categories', metadata, autoload_with=bind)

    with op.batch_alter_table('institutional_certificates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('categoria', sa.String(length=80), nullable=True))

    category_rows = bind.execute(sa.select(categories.c.id, categories.c.nome)).fetchall()
    category_id_to_name = {row.id: row.nome for row in category_rows}

    cert_rows = bind.execute(sa.select(certificates.c.id, certificates.c.category_id)).fetchall()
    for row in cert_rows:
        categoria = category_id_to_name.get(row.category_id, 'Sem Categoria')
        bind.execute(
            sa.text('UPDATE institutional_certificates SET categoria = :categoria WHERE id = :id'),
            {'categoria': categoria, 'id': row.id},
        )

    with op.batch_alter_table('institutional_certificates', schema=None) as batch_op:
        batch_op.drop_index('ix_institutional_cert_category_id')
        batch_op.drop_constraint('fk_institutional_certificates_category_id', type_='foreignkey')
        batch_op.create_index('ix_institutional_cert_categoria', ['categoria'], unique=False)
        batch_op.drop_column('category_id')

    op.drop_table('institutional_certificate_categories')
