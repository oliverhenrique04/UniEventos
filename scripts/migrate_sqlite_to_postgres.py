from pathlib import Path
import argparse
import re
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models import Activity, Course, Enrollment, Event, User

DEFAULT_SOURCE = f"sqlite:///{Path(__file__).resolve().parents[1] / 'sistema_academico.db'}"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Copy data from the legacy SQLite database to PostgreSQL using SQLAlchemy models."
    )
    parser.add_argument("--source-uri", default=DEFAULT_SOURCE, help="SQLAlchemy source database URI")
    parser.add_argument("--target-uri", required=True, help="SQLAlchemy target database URI")
    return parser.parse_args()


def row_to_dict(instance):
    return {column.name: getattr(instance, column.name) for column in instance.__table__.columns}


def _ensure_missing_event_owners(source_session, target_session):
    source_usernames = {
        username for username in source_session.scalars(select(User.username)).all() if username
    }
    owner_usernames = {
        owner for owner in source_session.scalars(select(Event.owner_username)).all() if owner
    }

    created = 0
    for owner_username in sorted(owner_usernames - source_usernames):
        placeholder = User(
            username=owner_username,
            email=None,
            password_hash=None,
            role='professor',
            nome=f'Usuário migrado ({owner_username})',
            cpf=None,
            ra=None,
            curso=None,
            course_id=None,
            can_create_events=False,
        )
        target_session.merge(placeholder)
        created += 1

    target_session.flush()
    return created


def _ensure_missing_enrollment_users(source_session, target_session):
    source_cpfs = {cpf for cpf in source_session.scalars(select(User.cpf)).all() if cpf}
    enrollment_cpfs = {
        cpf for cpf in source_session.scalars(select(Enrollment.user_cpf)).all() if cpf
    }

    created = 0
    for cpf in sorted(enrollment_cpfs - source_cpfs):
        suffix = re.sub(r'\D', '', cpf) or 'semcpf'
        placeholder = User(
            username=f'migrated_{suffix}',
            email=None,
            password_hash=None,
            role='participante',
            nome=f'Participante migrado {cpf}',
            cpf=cpf,
            ra=None,
            curso=None,
            course_id=None,
            can_create_events=False,
        )
        target_session.merge(placeholder)
        created += 1

    target_session.flush()
    return created


def copy_table(model, source_session, target_session):
    rows = source_session.execute(select(model)).scalars().all()
    for row in rows:
        target_session.merge(model(**row_to_dict(row)))
    target_session.flush()
    return len(rows)


def run_migration(source_uri, target_uri):
    source_engine = create_engine(source_uri)
    target_engine = create_engine(target_uri)

    source_session_factory = sessionmaker(bind=source_engine)
    target_session_factory = sessionmaker(bind=target_engine)

    copied = {}
    with source_session_factory() as source_session, target_session_factory() as target_session:
        copied[Course.__tablename__] = copy_table(Course, source_session, target_session)
        copied[User.__tablename__] = copy_table(User, source_session, target_session)
        copied['placeholder_event_owners'] = _ensure_missing_event_owners(source_session, target_session)
        copied['placeholder_enrollment_users'] = _ensure_missing_enrollment_users(source_session, target_session)
        copied[Event.__tablename__] = copy_table(Event, source_session, target_session)
        copied[Activity.__tablename__] = copy_table(Activity, source_session, target_session)
        copied[Enrollment.__tablename__] = copy_table(Enrollment, source_session, target_session)
        target_session.commit()

    return copied


def main():
    args = parse_args()
    copied = run_migration(args.source_uri, args.target_uri)

    print("Migration completed successfully.")
    for table_name, count in copied.items():
        print(f"- {table_name}: {count} row(s)")


if __name__ == "__main__":
    main()
