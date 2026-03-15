from datetime import date, datetime, time

from app.extensions import db
from app.models import Activity, Course, Enrollment, Event, User
from app.services.certificate_service import CertificateService


TUTORIAL_COURSE_NAME = "Ciência da Computação"
TUTORIAL_EVENT_NAME = "Evento Tutorial do Participante"
TUTORIAL_EVENT_TOKEN = "tutorial-participante"
TUTORIAL_COORDINATES = {
    "latitude": -15.793889,
    "longitude": -47.882778,
}
TUTORIAL_ACTIVITY_WELCOME = "Palestra de Boas-vindas"
TUTORIAL_ACTIVITY_CHECKIN = "Oficina de Check-in e Inscrição"


TUTORIAL_USERS = [
    {
        "username": "admin",
        "nome": "Administrador Geral",
        "email": "admin@unieuro.edu.br",
        "role": "admin",
        "cpf": "000.000.000-00",
        "ra": "ADMIN-001",
        "password": "admin",
        "bind_course": False,
    },
    {
        "username": "prof.ana",
        "nome": "Dra. Ana Silva",
        "email": "prof.ana@unieuro.edu.br",
        "role": "professor",
        "cpf": "111.222.333-44",
        "ra": "PROF-001",
        "password": "1234",
        "bind_course": True,
    },
    {
        "username": "coord.marcos",
        "nome": "Msc. Marcos Oliveira",
        "email": "coord.marcos@unieuro.edu.br",
        "role": "coordenador",
        "cpf": "555.666.777-88",
        "ra": "COORD-001",
        "password": "1234",
        "bind_course": True,
    },
    {
        "username": "extensao",
        "nome": "Equipe Extensão",
        "email": "extensao@unieuro.edu.br",
        "role": "extensao",
        "cpf": "222.333.444-55",
        "ra": "EXT-001",
        "password": "1234",
        "bind_course": False,
    },
    {
        "username": "gestor",
        "nome": "Gestor Acadêmico",
        "email": "gestor@unieuro.edu.br",
        "role": "gestor",
        "cpf": "999.888.777-66",
        "ra": "GEST-001",
        "password": "1234",
        "bind_course": True,
    },
    {
        "username": "aluno.demo",
        "nome": "Aluno Demonstracao",
        "email": "aluno.demo@unieuro.edu.br",
        "role": "participante",
        "cpf": "444.555.666-77",
        "ra": "20260001",
        "password": "1234",
        "bind_course": True,
    },
]


def tutorial_default_settings(base_url=None):
    resolved_base_url = base_url or "http://127.0.0.1:5000"
    participant = next(user for user in TUTORIAL_USERS if user["role"] == "participante")
    return {
        "base_url": resolved_base_url.rstrip("/"),
        "participant": {
            "cpf": participant["cpf"],
            "password": participant["password"],
        },
    }


def _build_user(spec, course):
    user = User(
        username=spec["username"],
        nome=spec["nome"],
        email=spec["email"],
        role=spec["role"],
        cpf=spec["cpf"],
        ra=spec["ra"],
        course_id=course.id if spec["bind_course"] else None,
        can_create_events=spec["role"] in {"admin", "professor", "coordenador", "gestor"},
    )
    user.set_password(spec["password"])
    return user


def _seed_tutorial_entities():
    course = Course(nome=TUTORIAL_COURSE_NAME)
    db.session.add(course)
    db.session.flush()

    users = {}
    for spec in TUTORIAL_USERS:
        user = _build_user(spec, course)
        db.session.add(user)
        users[user.username] = user

    db.session.flush()

    today = date.today()
    event = Event(
        owner_username="admin",
        nome=TUTORIAL_EVENT_NAME,
        descricao=(
            "Evento de demonstração utilizado para o tutorial oficial do participante. "
            "Ele reúne um fluxo de inscrição, confirmação de presença e emissão de certificados."
        ),
        tipo="PADRAO",
        data_inicio=today,
        hora_inicio=time(8, 0),
        data_fim=today,
        hora_fim=time(12, 0),
        token_publico=TUTORIAL_EVENT_TOKEN,
        status="ABERTO",
        course_id=course.id,
        latitude=TUTORIAL_COORDINATES["latitude"],
        longitude=TUTORIAL_COORDINATES["longitude"],
    )
    db.session.add(event)
    db.session.flush()

    activity_one = Activity(
        event_id=event.id,
        nome=TUTORIAL_ACTIVITY_WELCOME,
        palestrante="Dra. Ana Silva",
        local="Auditório Central",
        descricao="Atividade inicial já concluída para demonstrar histórico e certificado emitido.",
        data_atv=today,
        hora_atv=time(8, 30),
        carga_horaria=2,
        vagas=80,
    )
    activity_two = Activity(
        event_id=event.id,
        nome=TUTORIAL_ACTIVITY_CHECKIN,
        palestrante="Msc. Marcos Oliveira",
        local="Laboratório 01",
        descricao="Atividade usada para demonstrar inscrição e confirmação de presença no tutorial.",
        data_atv=today,
        hora_atv=time(10, 30),
        carga_horaria=2,
        vagas=40,
        latitude=TUTORIAL_COORDINATES["latitude"],
        longitude=TUTORIAL_COORDINATES["longitude"],
    )
    db.session.add_all([activity_one, activity_two])
    db.session.flush()

    student = users["aluno.demo"]
    initial_enrollment = Enrollment(
        activity_id=activity_one.id,
        user_cpf=student.cpf,
        nome=student.nome,
        presente=True,
        lat_checkin=TUTORIAL_COORDINATES["latitude"],
        lon_checkin=TUTORIAL_COORDINATES["longitude"],
    )
    db.session.add(initial_enrollment)
    db.session.commit()

    cert_service = CertificateService()
    cert_service.generate_pdf(
        event=event,
        user=student,
        activities=[activity_one],
        total_hours=activity_one.carga_horaria or 0,
        enrollment=initial_enrollment,
    )

    refreshed_enrollment = db.session.get(Enrollment, initial_enrollment.id)
    refreshed_enrollment.cert_entregue = True
    refreshed_enrollment.cert_data_envio = datetime.now()
    db.session.commit()

    return {
        "course_id": course.id,
        "event_id": event.id,
        "activity_welcome_id": activity_one.id,
        "activity_checkin_id": activity_two.id,
        "participant_username": student.username,
        "participant_cpf": student.cpf,
        "event_token": event.token_publico,
    }


def reset_tutorial_database():
    db.session.remove()
    db.drop_all()
    db.create_all()

    scenario = _seed_tutorial_entities()
    return {
        "users": User.query.count(),
        "courses": Course.query.count(),
        "events": Event.query.count(),
        "activities": Activity.query.count(),
        "enrollments": Enrollment.query.count(),
        "scenario": scenario,
    }


def get_tutorial_runtime_context():
    event = Event.query.filter_by(nome=TUTORIAL_EVENT_NAME).first()
    participant = User.query.filter_by(username="aluno.demo").first()
    activity_one = Activity.query.filter_by(nome=TUTORIAL_ACTIVITY_WELCOME).first()
    activity_two = Activity.query.filter_by(nome=TUTORIAL_ACTIVITY_CHECKIN).first()

    return {
        "event_id": event.id if event else None,
        "event_token": event.token_publico if event else None,
        "participant_username": participant.username if participant else None,
        "participant_cpf": participant.cpf if participant else None,
        "activity_welcome_id": activity_one.id if activity_one else None,
        "activity_checkin_id": activity_two.id if activity_two else None,
        "coordinates": dict(TUTORIAL_COORDINATES),
    }
