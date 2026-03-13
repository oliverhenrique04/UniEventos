from app.extensions import db
from app.models import User


def seed_default_users():
    """Seed baseline local users if they do not exist yet."""
    default_users = [
        {
            "username": "admin",
            "email": "admin@example.com",
            "role": "admin",
            "nome": "Super Admin",
            "cpf": "000.000.000-00",
            "ra": "ADMIN-001",
            "curso": "TI",
            "password": "admin",
        },
        {
            "username": "coord",
            "email": "coord@example.com",
            "role": "coordenador",
            "nome": "Coord. UniEventos",
            "cpf": "333.333.333-33",
            "ra": "COORD-001",
            "curso": "TI",
            "password": "1234",
        },
        {
            "username": "prof",
            "email": "prof@example.com",
            "role": "professor",
            "nome": "Prof. Pardal",
            "cpf": "111.111.111-11",
            "ra": "PROF-001",
            "curso": "Engenharia",
            "password": "1234",
        },
        {
            "username": "aluno",
            "email": "aluno@example.com",
            "role": "participante",
            "nome": "Lucas Aluno",
            "cpf": "222.222.222-22",
            "ra": "20260001",
            "curso": "Direito",
            "password": "1234",
        },
    ]

    created_count = 0
    for user_data in default_users:
        existing = User.query.filter_by(username=user_data["username"]).first()
        if existing:
            continue

        password = user_data.pop("password")
        user = User(**user_data)
        user.set_password(password)
        db.session.add(user)
        created_count += 1

    if created_count:
        db.session.commit()

    return created_count
