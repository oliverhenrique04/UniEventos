import click
from flask.cli import with_appcontext
from flask import current_app
from flask_migrate import upgrade

from app.bootstrap import seed_default_users
from app.extensions import db
from scripts.migrate_sqlite_to_postgres import run_migration, DEFAULT_SOURCE


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Create tables for the configured database."""
    db.create_all()
    click.echo("Database tables created.")


@click.command("seed-dev-data")
@with_appcontext
def seed_dev_data_command():
    """Seed baseline development users."""
    created = seed_default_users()
    if created:
        click.echo(f"Seed completed. Created {created} user(s).")
    else:
        click.echo("Seed skipped. Default users already exist.")


@click.command("bootstrap-postgres")
@click.option(
    "--source-uri",
    default=DEFAULT_SOURCE,
    show_default=True,
    help="SQLAlchemy URI do banco SQLite legado.",
)
@click.option(
    "--target-uri",
    default=None,
    help="SQLAlchemy URI do PostgreSQL alvo (padrao: SQLALCHEMY_DATABASE_URI).",
)
@click.option(
    "--skip-data",
    is_flag=True,
    default=False,
    help="Ignora a migracao de dados e aplica apenas o schema.",
)
@with_appcontext
def bootstrap_postgres_command(source_uri, target_uri, skip_data):
    """Apply migrations and optionally migrate data from SQLite to PostgreSQL."""
    resolved_target = target_uri or current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if not resolved_target:
        raise click.ClickException("SQLALCHEMY_DATABASE_URI nao configurado.")
    if resolved_target.startswith('sqlite'):
        raise click.ClickException("bootstrap-postgres requer um destino PostgreSQL.")

    click.echo("Aplicando migrations...")
    upgrade()
    click.echo("Schema aplicado.")

    if skip_data:
        click.echo("Migracao de dados ignorada (--skip-data).")
        return

    click.echo("Migrando dados do SQLite para PostgreSQL...")
    copied = run_migration(source_uri, resolved_target)
    click.echo("Migracao concluida.")
    for table_name, count in copied.items():
        click.echo(f"- {table_name}: {count} row(s)")


def register_cli(app):
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_dev_data_command)
    app.cli.add_command(bootstrap_postgres_command)
