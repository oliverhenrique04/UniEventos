# seed_large_with_enrollments.py
from app import create_app, db
from app.models import User, Event, Activity, Enrollment
from datetime import datetime, timedelta
import secrets
import hashlib

TARGET_USERS = 1000
TARGET_EVENTS = 500
MIN_PARTICIPANTS_PER_EVENT = 300

DEFAULT_PASSWORD = "1234"

CURSOS = [
    "Ciência da Computação",
    "Sistemas de Informação",
    "Engenharia",
    "Direito",
    "Medicina",
    "Arquitetura",
    "Administração",
    "Enfermagem",
]

LOCAIS = [
    "Auditório Central",
    "Lab 01",
    "Lab 02",
    "Sala 101",
    "Sala 202",
    "Bloco A - Sala 12",
    "Bloco B - Sala 07",
]

PALESTRANTES = [
    "Profa. Ana Silva",
    "Prof. Marcos Oliveira",
    "Dr. João Pereira",
    "Dra. Carla Mendes",
    "Msc. Pedro Henrique",
    "Convidado Externo",
]


def generate_valid_cpf(seed_int: int) -> str:
    """
    Gera CPF válido (com dígitos verificadores) e formata XXX.XXX.XXX-YY.
    Determinístico a partir de seed_int.
    """
    base = f"{(seed_int * 7919) % 10**9:09d}"
    nums = [int(x) for x in base]

    def dv_calc(n):
        s = sum(v * w for v, w in zip(n, range(len(n) + 1, 1, -1)))
        r = (s * 10) % 11
        return 0 if r == 10 else r

    dv1 = dv_calc(nums)
    dv2 = dv_calc(nums + [dv1])

    cpf = nums + [dv1, dv2]
    cpf_str = "".join(map(str, cpf))
    return f"{cpf_str[0:3]}.{cpf_str[3:6]}.{cpf_str[6:9]}-{cpf_str[9:11]}"


def presence_deterministic(event_id: int, cpf: str, threshold: int = 80) -> bool:
    """
    Presença determinística (idempotente): ~threshold% True.
    """
    h = hashlib.sha256(f"{event_id}-{cpf}".encode("utf-8")).hexdigest()
    val = int(h[:8], 16) % 100
    return val < threshold


def upsert_fixed_users():
    fixed = [
        ("admin", "Administrador Geral", "000.000.000-00", "ADMIN-001", "TI", "admin", "admin"),
        ("prof.ana", "Dra. Ana Silva", "111.222.333-44", "PROF-001", "Ciência da Computação", "professor", "1234"),
        ("coord.marcos", "Msc. Marcos Oliveira", "555.666.777-88", "COORD-001", "Engenharia", "coordenador", "1234"),
    ]

    for username, nome, cpf, ra, curso, role, pwd in fixed:
        user = User.query.filter(
            (User.username == username) |
            (User.cpf == cpf) |
            (User.ra == ra)
        ).first()

        if not user:
            user = User(
                username=username,
                nome=nome,
                email=f"{username}@unieuro.edu.br",
                cpf=cpf,
                ra=ra,
                curso=curso,
                role=role
            )
            user.set_password(pwd)
            db.session.add(user)
        else:
            user.nome = nome
            user.email = f"{username}@unieuro.edu.br"
            user.cpf = cpf
            user.ra = ra
            user.curso = curso
            user.role = role


def upsert_bulk_users(target_users: int):
    """
    Cria/atualiza usuários determinísticos: user0001..user1000 (role=participante)
    """
    reserved_cpfs = {u.cpf for u in User.query.filter(User.cpf.isnot(None)).all()}

    for i in range(1, target_users + 1):
        username = f"user{i:04d}"
        nome = f"Usuario {i:04d}"
        # offset alto para reduzir chance de colidir com CPFs já existentes
        cpf = generate_valid_cpf(i + 100000)
        while cpf in reserved_cpfs:
            # pequena variação determinística em caso de colisão rara
            cpf = generate_valid_cpf(i + 200000)
            break

        ra = f"2026{i:04d}"  # 20260001..20261000
        curso = CURSOS[(i - 1) % len(CURSOS)]
        role = "participante"
        email = f"{username}@unieuro.edu.br"

        user = User.query.filter(
            (User.username == username) |
            (User.cpf == cpf) |
            (User.ra == ra)
        ).first()

        if not user:
            user = User(
                username=username,
                nome=nome,
                email=email,
                cpf=cpf,
                ra=ra,
                curso=curso,
                role=role
            )
            user.set_password(DEFAULT_PASSWORD)
            db.session.add(user)
        else:
            user.nome = nome
            user.email = email
            user.cpf = cpf
            user.ra = ra
            user.curso = curso
            user.role = role

        reserved_cpfs.add(cpf)


def upsert_events(target_events: int):
    owners = ["admin", "prof.ana", "coord.marcos"]
    base_start = datetime(2026, 2, 10, 8, 0, 0)

    for i in range(1, target_events + 1):
        nome_evento = f"Evento {i:04d}"
        owner = owners[(i - 1) % len(owners)]
        tipo = "PADRAO" if (i % 2 == 0) else "RAPIDO"

        start_dt = base_start + timedelta(days=i)
        end_dt = start_dt if tipo == "RAPIDO" else (start_dt + timedelta(days=2))

        data_inicio = start_dt.strftime("%Y-%m-%d")
        hora_inicio = start_dt.strftime("%H:%M")
        data_fim = end_dt.strftime("%Y-%m-%d")
        hora_fim = "18:00"

        ev = Event.query.filter_by(nome=nome_evento).first()
        if not ev:
            ev = Event(
                owner_username=owner,
                nome=nome_evento,
                descricao=f"Descricao automatica para {nome_evento}.",
                tipo=tipo,
                data_inicio=data_inicio,
                hora_inicio=hora_inicio,
                data_fim=data_fim,
                hora_fim=hora_fim,
                token_publico=secrets.token_urlsafe(8),
                status="ABERTO",
            )
            db.session.add(ev)
            db.session.flush()

            # Cria 1 a 3 atividades por evento (determinístico)
            num_atvs = 1 + (i % 9)
            for k in range(1, num_atvs + 1):
                atv_nome = f"Atividade {k} - {nome_evento}"
                palestrante = PALESTRANTES[(i + k) % len(PALESTRANTES)]
                local = LOCAIS[(i + 2 * k) % len(LOCAIS)]
                carga = 2 if tipo == "RAPIDO" else (2 + (k % 3) * 2)

                # Para suportar 300 inscrições sem restrição
                vagas = -1

                a = Activity(
                    event_id=ev.id,
                    nome=atv_nome,
                    palestrante=palestrante,
                    local=local,
                    data_atv=data_inicio,
                    hora_atv=hora_inicio,
                    carga_horaria=carga,
                    vagas=vagas
                )
                db.session.add(a)
        else:
            ev.owner_username = owner
            ev.tipo = tipo
            ev.data_inicio = data_inicio
            ev.hora_inicio = hora_inicio
            ev.data_fim = data_fim
            ev.hora_fim = hora_fim
            ev.status = "ABERTO"
            if not ev.token_publico:
                ev.token_publico = secrets.token_urlsafe(8)
            if not ev.descricao:
                ev.descricao = f"Descricao automatica para {nome_evento}."


def ensure_min_participants_per_event(min_participants: int):
    participants = (
        User.query.filter_by(role="participante")
        .order_by(User.cpf.asc())
        .all()
    )
    if len(participants) < min_participants:
        raise RuntimeError(
            f"Usuarios participantes insuficientes: {len(participants)}. "
            f"Necessario ao menos {min_participants}."
        )

    cpf_list = [u.cpf for u in participants]
    cpf_to_name = {u.cpf: u.nome for u in participants}

    events = (
        Event.query
        .filter(Event.nome.like("Evento %"))
        .order_by(Event.id.asc())
        .all()
    )

    for idx, ev in enumerate(events, start=1):
        # Activity primária do evento
        primary = (
            Activity.query
            .filter_by(event_id=ev.id)
            .order_by(Activity.id.asc())
            .first()
        )
        if not primary:
            primary = Activity(
                event_id=ev.id,
                nome=f"Check-in - {ev.nome}",
                palestrante="Coordenacao",
                local="Auditório Central",
                data_atv=ev.data_inicio,
                hora_atv=ev.hora_inicio,
                carga_horaria=2,
                vagas=-1
            )
            db.session.add(primary)
            db.session.flush()

        # Garante vagas ilimitadas ou suficientes (se houver lógica no app)
        if primary.vagas is not None and primary.vagas != -1 and primary.vagas < min_participants:
            primary.vagas = -1

        existing_cpfs = {
            cpf for (cpf,) in (
                Enrollment.query
                .filter_by(activity_id=primary.id)
                .with_entities(Enrollment.user_cpf)
                .all()
            )
        }

        need = max(0, min_participants - len(existing_cpfs))
        if need == 0:
            # Commit em lotes para reduzir memória em seeds grandes
            if idx % 25 == 0:
                db.session.commit()
            continue

        # Seleção determinística de CPFs por evento (rotação)
        offset = (ev.id * 137) % len(cpf_list)

        selected = []
        j = 0
        while len(selected) < need and j < len(cpf_list):
            cpf = cpf_list[(offset + j) % len(cpf_list)]
            if cpf not in existing_cpfs:
                selected.append(cpf)
                existing_cpfs.add(cpf)
            j += 1

        for cpf in selected:
            en = Enrollment(
                activity_id=primary.id,
                event_id=ev.id,
                user_cpf=cpf,
                nome=cpf_to_name.get(cpf, "Participante"),
                presente=presence_deterministic(ev.id, cpf, threshold=80),
                cert_hash=None,
                cert_entregue=False,
                cert_data_envio=None,
                cert_email_alternativo=None
            )
            db.session.add(en)

        if idx % 25 == 0:
            db.session.commit()

    db.session.commit()


def run_seed_large():
    app = create_app()
    with app.app_context():
        print("Iniciando seed grande (idempotente).")

        upsert_fixed_users()
        db.session.commit()

        upsert_bulk_users(TARGET_USERS)
        db.session.commit()
        print(f"Usuarios totais: {User.query.count()}")

        upsert_events(TARGET_EVENTS)
        db.session.commit()
        print(f"Eventos totais: {Event.query.count()}")
        print(f"Atividades totais: {Activity.query.count()}")

        ensure_min_participants_per_event(MIN_PARTICIPANTS_PER_EVENT)
        print("Inscricoes garantidas.")
        print(f"Inscricoes totais: {Enrollment.query.count()}")

        print("Seed finalizado.")


if __name__ == "__main__":
    run_seed_large()
