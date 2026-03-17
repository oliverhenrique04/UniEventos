import json
from io import BytesIO
from datetime import date, time
from app.models import (
    Event,
    Activity,
    Enrollment,
    EventRegistration,
    Course,
    User,
    InstitutionalCertificateCategory,
    InstitutionalCertificate,
    InstitutionalCertificateRecipient,
)
from app.extensions import db
from openpyxl import Workbook
from app.services.auth_service import AuthService
from app.services.event_service import EventService
from app.api import admin as admin_api
from app.api import certificates as certificates_api


def _login_user(client, username, password='1234'):
    client.post('/api/login', json={'username': username, 'password': password})


def _login_admin(client):
    _login_user(client, 'admin_test')


def _extract_main_nav(html):
    start = html.index('<nav class="navbar navbar-expand-lg app-navbar sticky-top">')
    end = html.index('</nav>', start)
    return html[start:end]


def _create_event_for_certs(app, owner_username='admin_test'):
    with app.app_context():
        event = Event(
            owner_username=owner_username,
            nome='Evento Certificado',
            descricao='Teste',
            tipo='RAPIDO',
            data_inicio=date(2030, 1, 1),
            hora_inicio=time(10, 0)
        )
        from app.extensions import db
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            nome='Check-in Presenca',
            descricao='Atividade padrao do evento',
            data_atv=date(2030, 1, 1),
            hora_atv=time(10, 0),
            carga_horaria=4,
            vagas=100,
        )
        db.session.add(activity)
        db.session.commit()
        return event.id


def _seed_certificate_management_data(app):
    with app.app_context():
        course = Course(nome='Gestao de Certificados')
        db.session.add(course)
        db.session.flush()

        owner = User(
            username='cert_owner_user',
            role='professor',
            nome='Owner Certificados',
            cpf='70080090010',
            email='owner_certs@test.local',
            course_id=course.id,
            can_create_events=True,
        )
        owner.set_password('1234')

        coordinator = User(
            username='cert_coord_user',
            role='coordenador',
            nome='Coordenadora Certificados',
            cpf='70080090011',
            email='coord_certs@test.local',
            course_id=course.id,
        )
        coordinator.set_password('1234')

        manager = User(
            username='cert_manager_user',
            role='gestor',
            nome='Gestor Certificados',
            cpf='70080090012',
            email='manager_certs@test.local',
            course_id=course.id,
        )
        manager.set_password('1234')

        extension = User(
            username='cert_extension_user',
            role='extensao',
            nome='Extensao Certificados',
            cpf='70080090015',
            email='extension_certs@test.local',
            course_id=course.id,
        )
        extension.set_password('1234')

        participant = User(
            username='cert_participant_user',
            role='participante',
            nome='Participante Certificados',
            cpf='70080090013',
            email='participant_certs@test.local',
            course_id=course.id,
        )
        participant.set_password('1234')

        outsider = User(
            username='cert_outsider_user',
            role='participante',
            nome='Outro Participante',
            cpf='70080090014',
            email='outsider_certs@test.local',
            course_id=course.id,
        )
        outsider.set_password('1234')

        db.session.add_all([owner, coordinator, manager, extension, participant, outsider])
        db.session.flush()

        event = Event(
            owner_username=owner.username,
            nome='Evento Gestao Certificados',
            descricao='Teste de permissao de certificados',
            tipo='PADRAO',
            data_inicio=date(2030, 2, 1),
            hora_inicio=time(19, 0),
            data_fim=date(2030, 2, 1),
            hora_fim=time(21, 0),
            course_id=course.id,
        )
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            nome='Painel Principal',
            palestrante='Dra. Principal',
            email_palestrante='principal@example.com',
            local='Auditorio',
            descricao='Sessao principal',
            data_atv=date(2030, 2, 1),
            hora_atv=time(19, 30),
            carga_horaria=2,
            vagas=100,
        )
        db.session.add(activity)
        db.session.flush()

        enrollment = Enrollment(
            activity_id=activity.id,
            user_cpf=participant.cpf,
            nome=participant.nome,
            presente=True,
            cert_hash='CERTMANAGEMENT001',
        )
        db.session.add(enrollment)
        db.session.commit()

        return {
            'event_id': event.id,
            'activity_id': activity.id,
            'enrollment_id': enrollment.id,
            'owner_username': owner.username,
            'coordinator_username': coordinator.username,
            'manager_username': manager.username,
            'extension_username': extension.username,
            'participant_username': participant.username,
            'outsider_username': outsider.username,
        }


def _seed_manual_enrollment_data(app, participant_email='manual_api@test.local'):
    with app.app_context():
        extension_user = User(
            username='manual_api_extensao',
            role='extensao',
            nome='Extensao Manual API',
            cpf='22233344456',
            email='manual_extensao@test.local',
        )
        extension_user.set_password('1234')
        db.session.add(extension_user)

        participant = User(
            username='manual_api_user',
            role='participante',
            nome='Participante API',
            cpf='22233344455',
            email=participant_email,
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.flush()

        event = Event(
            owner_username='admin_test',
            nome='Evento API Manual',
            descricao='Evento para inscricao manual via API',
            tipo='PADRAO',
            token_publico='token-api-manual',
            data_inicio=date(2030, 6, 15),
            hora_inicio=time(18, 0),
        )
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            nome='Atividade API Manual',
            local='Sala API',
            descricao='Descricao atividade API',
            data_atv=date(2030, 6, 16),
            hora_atv=time(19, 0),
            carga_horaria=3,
            vagas=50,
        )
        db.session.add(activity)
        db.session.commit()

        return {
            'cpf': participant.cpf,
            'activity_id': activity.id,
            'participant_name': participant.nome,
            'extension_username': extension_user.username,
        }


def _login_participant(client):
    _login_user(client, 'participant_test')


def _seed_dashboard_analytics_data(app):
    with app.app_context():
        course_eng = Course(nome='Engenharia')
        course_dir = Course(nome='Direito')
        category = InstitutionalCertificateCategory(nome='Extensao')
        db.session.add_all([course_eng, course_dir, category])
        db.session.flush()

        users = [
            User(username='coord_analytics', role='coordenador', nome='Coord Analytics', cpf='20030040050', course_id=course_eng.id),
            User(username='coord_sem_curso', role='coordenador', nome='Coord Sem Curso', cpf='20030040051'),
            User(username='gestor_analytics', role='gestor', nome='Gestor Analytics', cpf='20030040052', course_id=course_eng.id),
            User(username='ext_analytics', role='extensao', nome='Extensao Analytics', cpf='20030040060', course_id=course_eng.id),
            User(username='prof_eng_a', role='professor', nome='Prof Eng A', cpf='20030040053', course_id=course_eng.id),
            User(username='prof_eng_b', role='professor', nome='Prof Eng B', cpf='20030040054', course_id=course_eng.id),
            User(username='prof_dir', role='professor', nome='Prof Dir', cpf='20030040055', course_id=course_dir.id),
            User(username='participant_dashboard', role='participante', nome='Participante Dashboard', cpf='20030040056', course_id=course_eng.id),
            User(username='student_eng_a', role='participante', nome='Aluno Eng A', cpf='20030040057', course_id=course_eng.id),
            User(username='student_eng_b', role='participante', nome='Aluno Eng B', cpf='20030040058', course_id=course_eng.id),
            User(username='student_dir', role='participante', nome='Aluno Dir', cpf='20030040059', course_id=course_dir.id),
        ]
        for user in users:
            user.set_password('1234')
        db.session.add_all(users)
        db.session.flush()

        today = date.today()
        event_eng_a = Event(
            owner_username='prof_eng_a',
            nome='Evento Engenharia A',
            descricao='Evento do curso de Engenharia',
            tipo='PADRAO',
            status='ABERTO',
            data_inicio=today,
            hora_inicio=time(9, 0),
            course_id=course_eng.id,
        )
        event_eng_b = Event(
            owner_username='prof_eng_b',
            nome='Evento Engenharia B',
            descricao='Evento do curso de Engenharia',
            tipo='RAPIDO',
            status='ENCERRADO',
            data_inicio=today,
            hora_inicio=time(14, 0),
            course_id=course_eng.id,
        )
        event_dir = Event(
            owner_username='prof_dir',
            nome='Evento Direito',
            descricao='Evento do curso de Direito',
            tipo='PADRAO',
            status='ABERTO',
            data_inicio=today,
            hora_inicio=time(16, 0),
            course_id=course_dir.id,
        )
        db.session.add_all([event_eng_a, event_eng_b, event_dir])
        db.session.flush()

        activity_eng_a = Activity(
            event_id=event_eng_a.id,
            nome='Atividade Engenharia A',
            descricao='Atividade do evento de Engenharia A',
            data_atv=today,
            hora_atv=time(9, 0),
            carga_horaria=4,
            vagas=50,
        )
        activity_eng_b = Activity(
            event_id=event_eng_b.id,
            nome='Atividade Engenharia B',
            descricao='Atividade do evento de Engenharia B',
            data_atv=today,
            hora_atv=time(14, 0),
            carga_horaria=3,
            vagas=50,
        )
        activity_dir = Activity(
            event_id=event_dir.id,
            nome='Atividade Direito',
            descricao='Atividade do evento de Direito',
            data_atv=today,
            hora_atv=time(16, 0),
            carga_horaria=2,
            vagas=50,
        )
        db.session.add_all([activity_eng_a, activity_eng_b, activity_dir])
        db.session.flush()

        db.session.add_all([
            Enrollment(
                activity_id=activity_eng_a.id,
                user_cpf='20030040057',
                nome='Aluno Eng A',
                presente=True,
                cert_hash='EVTENGA001',
            ),
            Enrollment(
                activity_id=activity_eng_b.id,
                user_cpf='20030040058',
                nome='Aluno Eng B',
                presente=False,
            ),
            Enrollment(
                activity_id=activity_dir.id,
                user_cpf='20030040059',
                nome='Aluno Dir',
                presente=True,
                cert_hash='EVTDIR001',
            ),
        ])

        cert_eng_a = InstitutionalCertificate(
            created_by_username='prof_eng_a',
            titulo='Certificado Engenharia A',
            category_id=category.id,
            descricao='Lote institucional Engenharia A',
            data_emissao=today.isoformat(),
            signer_name='Coord. Eng A',
            status='ENVIADO',
        )
        cert_eng_b = InstitutionalCertificate(
            created_by_username='prof_eng_b',
            titulo='Certificado Engenharia B',
            category_id=category.id,
            descricao='Lote institucional Engenharia B',
            data_emissao=today.isoformat(),
            signer_name='Coord. Eng B',
            status='RASCUNHO',
        )
        cert_dir = InstitutionalCertificate(
            created_by_username='prof_dir',
            titulo='Certificado Direito',
            category_id=category.id,
            descricao='Lote institucional Direito',
            data_emissao=today.isoformat(),
            signer_name='Coord. Direito',
            status='ARQUIVADO',
        )
        db.session.add_all([cert_eng_a, cert_eng_b, cert_dir])
        db.session.flush()

        db.session.add_all([
            InstitutionalCertificateRecipient(
                certificate_id=cert_eng_a.id,
                user_username='student_eng_a',
                nome='Aluno Eng A',
                email='eng_a@test.local',
                cpf='20030040057',
                cert_hash='INSTENGA001',
                cert_entregue=True,
            ),
            InstitutionalCertificateRecipient(
                certificate_id=cert_eng_a.id,
                user_username='student_dir',
                nome='Aluno Dir',
                email='dir_mix@test.local',
                cpf='20030040059',
                cert_hash='INSTMIX001',
                cert_entregue=False,
            ),
            InstitutionalCertificateRecipient(
                certificate_id=cert_eng_b.id,
                user_username='student_eng_b',
                nome='Aluno Eng B',
                email='eng_b@test.local',
                cpf='20030040058',
                cert_hash='INSTENGB001',
                cert_entregue=False,
            ),
            InstitutionalCertificateRecipient(
                certificate_id=cert_dir.id,
                user_username='student_dir',
                nome='Aluno Dir',
                email='dir@test.local',
                cpf='20030040059',
                cert_hash='INSTDIR001',
                cert_entregue=True,
            ),
        ])
        db.session.commit()

        return {
            'course_eng_id': course_eng.id,
            'course_dir_id': course_dir.id,
            'coord_username': 'coord_analytics',
            'coord_no_course_username': 'coord_sem_curso',
            'gestor_username': 'gestor_analytics',
            'extensao_username': 'ext_analytics',
            'prof_eng_a_username': 'prof_eng_a',
            'prof_eng_b_username': 'prof_eng_b',
            'prof_dir_username': 'prof_dir',
            'participant_username': 'participant_dashboard',
        }


def _build_students_xlsx_for_api(rows, include_email=True):
    wb = Workbook()
    ws = wb.active

    headers = [
        'ALUNO_NOME', 'IES', 'CURSO', 'TURMA', 'CPF', 'DATANASCIMENTO',
        'SEXO', 'ESTADOCIVIL', 'MAE', 'NIVEL ESCOLAR', 'RA', 'TURNO',
        'PERIODO', 'RUA_NUMERO', 'BAIRRO', 'CEP', 'MUNICIPIO', 'ESTADO',
        'Total Geral'
    ]
    if include_email:
        headers.append('EMAIL')

    ws.append(headers)
    for row in rows:
        ws.append(row)

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def _seed_profile_history_data(app):
    with app.app_context():
        participant = User(
            username='participant_test',
            role='participante',
            nome='Participante Teste',
            cpf='123.456.789-00',
            email='participant@test.local',
        )
        participant.set_password('1234')
        db.session.add(participant)

        category = InstitutionalCertificateCategory(nome='Extensao')
        db.session.add(category)
        db.session.flush()

        event = Event(
            owner_username='admin_test',
            nome='Evento Perfil',
            descricao='Teste de perfil',
            tipo='PADRAO',
            data_inicio=date(2030, 5, 10),
            hora_inicio=time(9, 0),
        )
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            nome='Atividade Perfil',
            palestrante='Docente',
            local='Sala 1',
            descricao='Atividade para timeline',
            data_atv=date(2030, 5, 10),
            hora_atv=time(10, 0),
            carga_horaria=4,
            vagas=100,
        )
        db.session.add(activity)
        db.session.flush()

        enrollment = Enrollment(
            activity_id=activity.id,
            user_cpf=participant.cpf,
            nome=participant.nome,
            presente=True,
            cert_hash='EVTHASH001',
        )
        db.session.add(enrollment)

        inst_cert = InstitutionalCertificate(
            created_by_username='admin_test',
            titulo='Certificado Institucional Perfil',
            category_id=category.id,
            descricao='Teste',
            data_emissao='2030-05-12',
            signer_name='Coord. NUTED',
            status='ENVIADO',
        )
        db.session.add(inst_cert)
        db.session.flush()

        inst_recipient = InstitutionalCertificateRecipient(
            certificate_id=inst_cert.id,
            user_username=participant.username,
            nome=participant.nome,
            email=participant.email,
            cpf=participant.cpf,
            metadata_json=json.dumps({'carga_horaria': '2'}),
            cert_hash='INSTHASH001',
            cert_entregue=True,
        )
        db.session.add(inst_recipient)

        db.session.commit()


def _seed_flagged_event_creator(app, username='participant_creator', role='participante'):
    with app.app_context():
        course = Course(nome=f'Curso {username}')
        db.session.add(course)
        db.session.flush()

        user = User(
            username=username,
            role=role,
            nome='Criador de Eventos',
            cpf='55566677788',
            email=f'{username}@test.local',
            course_id=course.id,
            can_create_events=True,
        )
        user.set_password('1234')
        db.session.add(user)
        db.session.commit()

        return {
            'username': username,
            'course_name': course.nome,
            'course_id': course.id,
        }


def _seed_open_events_access_data(app):
    with app.app_context():
        course = Course(nome='Eventos Abertos')
        db.session.add(course)
        db.session.flush()

        users = [
            User(username='open_participant', role='participante', nome='Participante Aberto', cpf='90100000001', email='open_participant@test.local', course_id=course.id),
            User(username='open_professor', role='professor', nome='Professor Aberto', cpf='90100000002', email='open_professor@test.local', course_id=course.id),
            User(username='open_coord', role='coordenador', nome='Coordenador Aberto', cpf='90100000003', email='open_coord@test.local', course_id=course.id),
            User(username='open_gestor', role='gestor', nome='Gestor Aberto', cpf='90100000004', email='open_gestor@test.local', course_id=course.id),
            User(username='open_extensao', role='extensao', nome='Extensao Aberta', cpf='90100000005', email='open_extensao@test.local', course_id=course.id),
        ]
        for user in users:
            user.set_password('1234')
        db.session.add_all(users)
        db.session.flush()

        open_event = Event(
            owner_username='admin_test',
            nome='Evento Aberto Geral',
            descricao='Disponivel para todos os perfis.',
            tipo='PADRAO',
            status='ABERTO',
            token_publico='evento-aberto-geral',
            data_inicio=date(2030, 8, 20),
            hora_inicio=time(9, 0),
            course_id=course.id,
        )
        closed_event = Event(
            owner_username='admin_test',
            nome='Evento Encerrado Geral',
            descricao='Nao deve aparecer na lista aberta.',
            tipo='PADRAO',
            status='ENCERRADO',
            token_publico='evento-encerrado-geral',
            data_inicio=date(2030, 8, 21),
            hora_inicio=time(10, 0),
            course_id=course.id,
        )
        db.session.add_all([open_event, closed_event])
        db.session.flush()

        open_activity = Activity(
            event_id=open_event.id,
            nome='Atividade Aberta',
            descricao='Atividade para inscricao ampla.',
            data_atv=date(2030, 8, 20),
            hora_atv=time(9, 0),
            carga_horaria=2,
            vagas=50,
        )
        closed_activity = Activity(
            event_id=closed_event.id,
            nome='Atividade Encerrada',
            descricao='Nao deve aparecer.',
            data_atv=date(2030, 8, 21),
            hora_atv=time(10, 0),
            carga_horaria=2,
            vagas=50,
        )
        db.session.add_all([open_activity, closed_activity])
        db.session.commit()

        return {
            'usernames': [
                'open_participant',
                'open_professor',
                'open_coord',
                'open_gestor',
                'open_extensao',
            ],
            'open_activity_id': open_activity.id,
            'open_event_name': open_event.nome,
            'open_extensao_cpf': '90100000005',
        }


def _seed_open_events_filter_data(app):
    with app.app_context():
        course_tech = Course(nome='Tecnologia Aplicada')
        course_law = Course(nome='Direito Corporativo')
        db.session.add_all([course_tech, course_law])
        db.session.flush()

        participant = User(
            username='filter_open_participant',
            role='participante',
            nome='Participante Filtro',
            cpf='90100000011',
            email='filter_open_participant@test.local',
            course_id=course_tech.id,
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.flush()

        event_python = Event(
            owner_username='admin_test',
            nome='Semana Python',
            descricao='Evento aberto de tecnologia.',
            tipo='PADRAO',
            status='ABERTO',
            token_publico='semana-python',
            data_inicio=date(2030, 9, 10),
            hora_inicio=time(19, 0),
            course_id=course_tech.id,
        )
        event_law = Event(
            owner_username='admin_test',
            nome='Seminario Juridico',
            descricao='Evento aberto da area juridica.',
            tipo='RAPIDO',
            status='ABERTO',
            token_publico='seminario-juridico',
            data_inicio=date(2030, 9, 25),
            hora_inicio=time(9, 0),
            course_id=course_law.id,
        )
        db.session.add_all([event_python, event_law])
        db.session.flush()

        activity_python = Activity(
            event_id=event_python.id,
            nome='Oficina de Automacao',
            palestrante='Profa. Maria Silva',
            local='Laboratorio Inovacao',
            descricao='Atividade pratica com scripts.',
            data_atv=date(2030, 9, 10),
            hora_atv=time(19, 30),
            carga_horaria=2,
            vagas=40,
        )
        activity_law = Activity(
            event_id=event_law.id,
            nome='Painel de Compliance',
            palestrante='Dr. Paulo Souza',
            local='Auditorio Juridico',
            descricao='Discussao institucional.',
            data_atv=date(2030, 9, 25),
            hora_atv=time(9, 30),
            carga_horaria=3,
            vagas=60,
        )
        db.session.add_all([activity_python, activity_law])
        db.session.flush()

        enrollment = Enrollment(
            activity_id=activity_python.id,
            user_cpf=participant.cpf,
            nome=participant.nome,
            presente=False,
        )
        db.session.add(enrollment)
        db.session.commit()

        return {
            'participant_username': participant.username,
            'course_tech_id': course_tech.id,
            'course_tech_name': course_tech.nome,
            'python_event_name': event_python.nome,
            'law_event_name': event_law.nome,
        }

def test_login_api(client, admin_user):
    res = client.post('/api/login', json={'username': 'admin_test', 'password': '1234'})
    assert res.status_code == 200
    assert res.json['status'] == 'success'

def test_login_fail(client):
    res = client.post('/api/login', json={'username': 'wrong', 'password': '123'})
    assert res.status_code == 401


def test_login_marks_session_as_permanent(client, admin_user):
    res = client.post('/api/login', json={'username': 'admin_test', 'password': '1234'})

    assert res.status_code == 200
    with client.session_transaction() as flask_session:
        assert flask_session.permanent is True
    assert client.application.permanent_session_lifetime.total_seconds() == 300


def test_session_ping_keeps_authenticated_session_alive(client, admin_user):
    _login_admin(client)

    res = client.get('/api/session/ping')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['status'] == 'ok'
    assert payload['session_timeout_minutes'] >= 1
    with client.session_transaction() as flask_session:
        assert flask_session.permanent is True


def test_protected_api_returns_401_json_when_not_authenticated(client):
    res = client.get('/api/eventos')

    assert res.status_code == 401
    assert res.is_json
    assert res.headers.get('X-Session-Expired') == '1'
    assert res.get_json()['session_expired'] is True


def test_dashboard_page_no_longer_renders_management_analytics(client, app, admin_user):
    seeded = _seed_dashboard_analytics_data(app)

    _login_admin(client)
    admin_html = client.get('/').get_data(as_text=True)
    assert 'Painel Analítico de Gestão' not in admin_html
    assert 'id="modalSessionWarning"' in admin_html
    assert 'id="btnSessionWarningKeepAlive"' in admin_html

    client.get('/api/logout')
    _login_user(client, seeded['gestor_username'])
    gestor_html = client.get('/').get_data(as_text=True)
    assert 'Painel Analítico de Gestão' not in gestor_html

    client.get('/api/logout')
    _login_user(client, seeded['coord_username'])
    coord_html = client.get('/').get_data(as_text=True)
    assert 'Painel Analítico de Gestão' not in coord_html

    client.get('/api/logout')
    _login_user(client, seeded['prof_eng_a_username'])
    professor_html = client.get('/').get_data(as_text=True)
    assert 'Painel Analítico de Gestão' not in professor_html

    client.get('/api/logout')
    _login_user(client, seeded['participant_username'])
    participante_html = client.get('/').get_data(as_text=True)
    assert 'Painel Analítico de Gestão' not in participante_html


def test_authenticated_navbar_keeps_mobile_collapse_and_role_links(client, app, admin_user):
    seeded = _seed_dashboard_analytics_data(app)

    _login_admin(client)
    admin_html = client.get('/').get_data(as_text=True)
    admin_nav = _extract_main_nav(admin_html)
    assert 'data-bs-toggle="collapse"' in admin_html
    assert 'data-bs-target="#navbarMain"' in admin_html
    assert 'aria-controls="navbarMain"' in admin_html
    assert 'collapse navbar-collapse app-navbar__panel' in admin_html
    assert 'href="/cursos"' in admin_nav
    assert 'href="/usuarios"' in admin_nav
    assert 'href="/analitico"' in admin_nav
    assert 'href="/eventos_admin"' in admin_nav

    client.get('/api/logout')
    _login_user(client, seeded['gestor_username'])
    gestor_nav = _extract_main_nav(client.get('/').get_data(as_text=True))
    assert 'href="/cursos"' in gestor_nav
    assert 'href="/usuarios"' in gestor_nav
    assert 'href="/analitico"' in gestor_nav
    assert 'href="/eventos_admin"' in gestor_nav

    client.get('/api/logout')
    _login_user(client, seeded['coord_username'])
    coord_nav = _extract_main_nav(client.get('/').get_data(as_text=True))
    assert 'href="/cursos"' not in coord_nav
    assert 'href="/usuarios"' not in coord_nav
    assert 'href="/analitico"' in coord_nav
    assert 'href="/eventos_admin"' in coord_nav

    with app.app_context():
        participant = db.session.get(User, seeded['participant_username'])
        participant.can_create_events = True
        db.session.commit()

    client.get('/api/logout')
    _login_user(client, seeded['participant_username'])
    creator_nav = _extract_main_nav(client.get('/').get_data(as_text=True))
    assert 'href="/eventos_admin"' in creator_nav
    assert 'href="/cursos"' not in creator_nav
    assert 'href="/usuarios"' not in creator_nav
    assert 'href="/analitico"' not in creator_nav

    with app.app_context():
        participant = db.session.get(User, seeded['participant_username'])
        participant.can_create_events = False
        db.session.commit()

    client.get('/api/logout')
    _login_user(client, seeded['participant_username'])
    participant_nav = _extract_main_nav(client.get('/').get_data(as_text=True))
    assert 'href="/eventos_admin"' not in participant_nav
    assert 'href="/cursos"' not in participant_nav
    assert 'href="/usuarios"' not in participant_nav
    assert 'href="/analitico"' not in participant_nav


def test_dashboard_hides_event_management_when_user_has_no_visible_records(client, admin_user):
    _login_admin(client)

    html = client.get('/').get_data(as_text=True)

    assert 'id="dashboard-eventos"' not in html
    assert '<h4 class="fw-bold mb-2">Gestão de Eventos</h4>' not in html


def test_dashboard_keeps_event_management_when_visible_records_exist(client, app, admin_user):
    _seed_dashboard_analytics_data(app)
    _login_admin(client)

    html = client.get('/').get_data(as_text=True)

    assert 'id="dashboard-eventos"' in html
    assert '<h4 class="fw-bold mb-2">Gestão de Eventos</h4>' in html


def test_analytics_page_visibility_by_role(client, app, admin_user):
    seeded = _seed_dashboard_analytics_data(app)

    _login_admin(client)
    admin_res = client.get('/analitico')
    admin_html = admin_res.get_data(as_text=True)
    assert admin_res.status_code == 200
    assert 'Painel Analítico de Gestão' in admin_html

    client.get('/logout')
    _login_user(client, seeded['gestor_username'])
    gestor_res = client.get('/analitico')
    gestor_html = gestor_res.get_data(as_text=True)
    assert gestor_res.status_code == 200
    assert 'Painel Analítico de Gestão' in gestor_html

    client.get('/logout')
    _login_user(client, seeded['coord_username'])
    coord_res = client.get('/analitico')
    coord_html = coord_res.get_data(as_text=True)
    assert coord_res.status_code == 200
    assert 'Painel Analítico de Gestão' in coord_html
    assert 'id="analyticsCourseFilter" disabled' in coord_html

    client.get('/logout')
    _login_user(client, seeded['prof_eng_a_username'])
    assert client.get('/analitico').status_code == 403

    client.get('/logout')
    _login_user(client, seeded['participant_username'])
    assert client.get('/analitico').status_code == 403


def test_dashboard_analytics_coordinator_is_scoped_to_own_course(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    _login_user(client, seeded['coord_username'])
    res = client.get(f"/api/dashboard/analytics?course_id={seeded['course_dir_id']}")

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['applied_filters']['course_id'] == seeded['course_eng_id']
    assert payload['summary']['total_events'] == 2
    assert payload['summary']['total_courses'] == 1
    assert payload['summary']['pending_certificate_events'] == 1
    assert payload['events_by_course'] == [{'course': 'Engenharia', 'count': 2}]
    assert payload['students_by_course'] == [{'course': 'Engenharia', 'count': 2}]
    assert {item['username'] for item in payload['filter_options']['owners']} == {
        seeded['prof_eng_a_username'],
        seeded['prof_eng_b_username'],
    }
    assert payload['institutional_summary']['total_certificates'] == 2
    assert payload['institutional_summary']['draft_certificates'] == 1
    assert payload['institutional_summary']['sent_certificates'] == 1
    assert payload['institutional_summary']['archived_certificates'] == 0
    assert payload['institutional_summary']['total_recipients'] == 2
    assert payload['institutional_summary']['delivered_recipients'] == 1
    assert payload['institutional_summary']['pending_recipients'] == 1


def test_dashboard_analytics_coordinator_owner_filter_stays_inside_course_scope(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    _login_user(client, seeded['coord_username'])
    res = client.get(f"/api/dashboard/analytics?owner_username={seeded['prof_eng_a_username']}")

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['applied_filters']['course_id'] == seeded['course_eng_id']
    assert payload['applied_filters']['owner_username'] == seeded['prof_eng_a_username']
    assert payload['summary']['total_events'] == 1
    assert payload['pending_certificate_events'] == []
    assert payload['institutional_summary']['total_certificates'] == 1
    assert payload['institutional_summary']['total_recipients'] == 1
    assert payload['institutional_summary']['delivered_recipients'] == 1
    assert payload['institutional_summary']['pending_recipients'] == 0


def test_dashboard_analytics_coordinator_without_course_returns_empty_payload(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    _login_user(client, seeded['coord_no_course_username'])
    res = client.get(
        f"/api/dashboard/analytics?course_id={seeded['course_eng_id']}&owner_username={seeded['prof_eng_a_username']}"
    )

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['summary']['total_events'] == 0
    assert payload['summary']['total_enrollments'] == 0
    assert payload['institutional_summary']['total_certificates'] == 0
    assert payload['applied_filters']['course_id'] is None
    assert payload['applied_filters']['owner_username'] == seeded['prof_eng_a_username']
    assert payload['filter_options']['owners'] == []


def test_dashboard_analytics_gestor_behavior_remains_unchanged(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    _login_user(client, seeded['gestor_username'])
    res = client.get(f"/api/dashboard/analytics?course_id={seeded['course_dir_id']}")

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['applied_filters']['course_id'] == seeded['course_dir_id']
    assert payload['summary']['total_events'] == 1
    assert payload['events_by_course'] == [{'course': 'Direito', 'count': 1}]
    assert payload['institutional_summary']['total_certificates'] == 3


def test_events_api_keeps_gestor_read_only_for_foreign_events(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    _login_user(client, seeded['gestor_username'])
    res = client.get('/api/eventos')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['total'] == 3
    assert {item['course_id'] for item in payload['items']} == {
        seeded['course_eng_id'],
        seeded['course_dir_id'],
    }
    assert all(item['can_edit'] is False for item in payload['items'])
    assert all(item['can_delete'] is False for item in payload['items'])
    assert all(item['can_manage_participants'] is False for item in payload['items'])
    assert all(item['can_view_certificates'] is True for item in payload['items'])
    assert all(item['can_manage_certificates'] is False for item in payload['items'])


def test_events_api_allows_coordinator_management_within_course_scope_without_delete(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    _login_user(client, seeded['coord_username'])
    res = client.get('/api/eventos')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['total'] == 2
    assert {item['course_id'] for item in payload['items']} == {seeded['course_eng_id']}
    assert all(item['can_edit'] is True for item in payload['items'])
    assert all(item['can_delete'] is False for item in payload['items'])
    assert all(item['can_manage_participants'] is True for item in payload['items'])
    assert all(item['can_manage_certificates'] is True for item in payload['items'])


def test_events_api_allows_extensao_participant_and_certificate_access_without_event_edit(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    _login_user(client, seeded['extensao_username'])
    page_res = client.get('/eventos_admin')
    assert page_res.status_code == 200
    page_html = page_res.get_data(as_text=True)
    assert 'events-admin-page' in page_html
    assert 'events-admin-main-table' in page_html
    assert 'participants-table' in page_html
    assert 'id="tabelaEventos"' in page_html
    assert 'id="modalParticipantes"' in page_html

    res = client.get('/api/eventos_admin')
    assert res.status_code == 200
    payload = res.get_json()
    assert payload['total'] == 3
    assert all(item['can_edit'] is False for item in payload['items'])
    assert all(item['can_delete'] is False for item in payload['items'])
    assert all(item['can_manage_participants'] is True for item in payload['items'])
    assert all(item['can_add_participants'] is True for item in payload['items'])
    assert all(item['can_notify_participants'] is False for item in payload['items'])
    assert all(item['can_manage_certificates'] is True for item in payload['items'])


def test_event_mutations_are_denied_for_non_owner_management_profiles(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    with app.app_context():
        event = Event.query.filter_by(owner_username=seeded['prof_eng_a_username']).first()
        assert event is not None
        event_id = event.id
        event_payload = {
            'id': event.id,
            'nome': event.nome,
            'descricao': event.descricao,
            'is_rapido': event.tipo == 'RAPIDO',
            'carga_horaria_rapida': 3 if event.tipo == 'RAPIDO' else None,
            'data_inicio': event.data_inicio.isoformat() if event.data_inicio else None,
            'hora_inicio': event.hora_inicio.strftime('%H:%M') if event.hora_inicio else None,
            'data_fim': event.data_fim.isoformat() if event.data_fim else None,
            'hora_fim': event.hora_fim.strftime('%H:%M') if event.hora_fim else None,
            'curso': event.curso,
            'atividades': [],
        }

    client.get('/api/logout')
    _login_user(client, seeded['gestor_username'])

    edit_res = client.post('/api/editar_evento', json={'id': event_id})
    delete_res = client.delete(f'/api/deletar_evento/{event_id}')

    assert edit_res.status_code == 403
    assert delete_res.status_code == 403

    client.get('/api/logout')
    _login_user(client, seeded['coord_username'])

    coord_edit_res = client.post('/api/editar_evento', json=event_payload)
    coord_delete_res = client.delete(f'/api/deletar_evento/{event_id}')

    assert coord_edit_res.status_code == 200
    assert coord_delete_res.status_code == 403

    client.get('/api/logout')
    _login_user(client, seeded['extensao_username'])

    extension_edit_res = client.post('/api/editar_evento', json=event_payload)
    extension_delete_res = client.delete(f'/api/deletar_evento/{event_id}')
    extension_notify_res = client.post(f'/api/notificar_participantes/{event_id}', json={
        'assunto': 'Comunicado',
        'mensagem': 'Mensagem de teste',
    })

    assert extension_edit_res.status_code == 403
    assert extension_delete_res.status_code == 403
    assert extension_notify_res.status_code == 403


def test_gestor_can_edit_and_delete_only_own_events(client, app):
    seeded = _seed_flagged_event_creator(app, username='gestor_owner_scope', role='gestor')

    _login_user(client, seeded['username'])
    create_res = client.post('/api/criar_evento', json={
        'nome': 'Evento do Gestor',
        'descricao': 'Evento proprio do gestor',
        'curso': seeded['course_name'],
        'is_rapido': True,
        'carga_horaria_rapida': 2,
        'data_inicio': '2030-09-01',
        'hora_inicio': '19:00',
    })

    assert create_res.status_code == 200

    with app.app_context():
        event = Event.query.filter_by(owner_username=seeded['username'], nome='Evento do Gestor').first()
        assert event is not None
        event_id = event.id

    edit_res = client.post('/api/editar_evento', json={
        'id': event_id,
        'nome': 'Evento do Gestor Atualizado',
        'descricao': 'Evento proprio atualizado',
        'is_rapido': True,
        'carga_horaria_rapida': 3,
        'data_inicio': '2030-09-02',
        'hora_inicio': '20:00',
    })
    assert edit_res.status_code == 200

    delete_res = client.delete(f'/api/deletar_evento/{event_id}')
    assert delete_res.status_code == 200


def test_delete_event_returns_400_and_admin_payload_blocks_when_event_has_registration(client, app, admin_user):
    with app.app_context():
        participant = User(
            username='event_delete_registration_participant',
            role='participante',
            nome='Participante Registro',
            cpf='30040050060',
            email='event_delete_registration@test.local',
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.commit()

        service = EventService()
        event = service.create_event('admin_test', {
            'nome': 'Evento API Bloqueado por Inscricao',
            'descricao': 'Evento com inscricao vinculada',
            'is_rapido': True,
            'carga_horaria_rapida': 2,
            'data_inicio': '2030-10-01',
            'hora_inicio': '19:00',
        })
        db.session.add(EventRegistration(
            event_id=event.id,
            user_cpf=participant.cpf,
            category_id=event.registration_categories[0].id,
        ))
        db.session.commit()
        event_id = event.id

    _login_admin(client)

    delete_res = client.delete(f'/api/deletar_evento/{event_id}')
    assert delete_res.status_code == 400
    assert delete_res.get_json() == {
        'erro': 'Não é possível excluir o evento porque existem inscrições ou matrículas vinculadas.',
        'linked_event_registrations_count': 1,
        'linked_enrollments_count': 0,
    }

    list_res = client.get('/api/eventos_admin')
    assert list_res.status_code == 200
    payload = list_res.get_json()
    blocked_item = next(item for item in payload['items'] if item['id'] == event_id)
    assert blocked_item['can_delete'] is False
    assert blocked_item['can_delete_permission'] is True
    assert blocked_item['linked_event_registrations_count'] == 1
    assert blocked_item['linked_enrollments_count'] == 0
    assert blocked_item['has_linked_records'] is True
    assert blocked_item['delete_block_reason'] == 'Não é possível excluir o evento porque existem inscrições ou matrículas vinculadas.'


def test_delete_event_returns_400_when_event_has_legacy_enrollment(client, app, admin_user):
    with app.app_context():
        participant = User(
            username='event_delete_legacy_participant',
            role='participante',
            nome='Participante Legado API',
            cpf='30040050061',
            email='event_delete_legacy@test.local',
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.commit()

        service = EventService()
        event = service.create_event('admin_test', {
            'nome': 'Evento API Bloqueado por Matricula',
            'descricao': 'Evento com matricula legada',
            'is_rapido': True,
            'carga_horaria_rapida': 2,
            'data_inicio': '2030-10-02',
            'hora_inicio': '19:00',
        })
        db.session.add(Enrollment(
            activity_id=event.activities[0].id,
            user_cpf=participant.cpf,
            nome=participant.nome,
            presente=False,
        ))
        db.session.commit()
        event_id = event.id

    _login_admin(client)

    delete_res = client.delete(f'/api/deletar_evento/{event_id}')
    assert delete_res.status_code == 400
    assert delete_res.get_json() == {
        'erro': 'Não é possível excluir o evento porque existem inscrições ou matrículas vinculadas.',
        'linked_event_registrations_count': 0,
        'linked_enrollments_count': 1,
    }


def test_dashboard_analytics_professor_owner_filter_remains_disabled(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    _login_user(client, seeded['prof_eng_a_username'])
    res = client.get(f"/api/dashboard/analytics?owner_username={seeded['prof_eng_b_username']}")

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['applied_filters']['owner_username'] is None
    assert payload['summary']['total_events'] == 1


def test_dashboard_analytics_participant_still_has_no_access(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    _login_user(client, seeded['participant_username'])
    res = client.get('/api/dashboard/analytics')
    assert res.status_code == 403

def test_user_crud_persists_can_create_events_flag(client, app, admin_user):
    with app.app_context():
        db.session.add(Course(nome='Curso Permissao'))
        db.session.commit()

    _login_admin(client)
    create_res = client.post('/api/criar_usuario', json={
        'username': 'user_flagged',
        'password': '1234',
        'nome': 'Usuario Flag',
        'email': 'user_flagged@test.local',
        'cpf': '12345678901',
        'ra': 'RA-FLAG-01',
        'curso': 'Curso Permissao',
        'role': 'participante',
        'can_create_events': True,
    })

    assert create_res.status_code == 200
    with app.app_context():
        created = db.session.get(User, '12345678901')
        assert created is not None
        assert created.can_create_events is True

    edit_res = client.post('/api/editar_usuario', json={
        'username_alvo': '12345678901',
        'nome': 'Usuario Flag',
        'email': 'user_flagged@test.local',
        'cpf': '12345678901',
        'ra': 'RA-FLAG-01',
        'curso': 'Curso Permissao',
        'role': 'participante',
        'can_create_events': False,
    })

    assert edit_res.status_code == 200
    with app.app_context():
        updated = db.session.get(User, '12345678901')
        assert updated.can_create_events is False


def test_import_users_csv_accepts_model_compatible_headers(client, app, admin_user):
    with app.app_context():
        db.session.add(Course(nome='Curso CSV Modelo'))
        db.session.commit()

    _login_admin(client)
    csv_content = (
        "nome,email,cpf,ra,role,curso,can_create_events,password\n"
        "Usuario CSV,csv_model@test.local,123.456.789-01,RA-CSV-01,professor,Curso CSV Modelo,sim,senha-segura\n"
    )

    res = client.post(
        '/api/importar_usuarios_csv',
        data={'file': (BytesIO(csv_content.encode('utf-8')), 'usuarios.csv')},
        content_type='multipart/form-data',
    )

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['importados'] == 1
    assert payload['erros'] == []

    with app.app_context():
        imported = db.session.get(User, '12345678901')
        assert imported is not None
        assert imported.nome == 'Usuario CSV'
        assert imported.email == 'csv_model@test.local'
        assert imported.cpf == '12345678901'
        assert imported.ra == 'RA-CSV-01'
        assert imported.role == 'professor'
        assert imported.curso == 'Curso CSV Modelo'
        assert imported.can_create_events is True
        assert imported.check_password('senha-segura') is True


def test_import_users_csv_keeps_legacy_aliases_and_reports_row_validation_errors(client, app, admin_user):
    with app.app_context():
        course = Course(nome='Curso CSV Legado')
        db.session.add(course)
        db.session.flush()

        existing = User(
            username='existing_csv_user',
            role='participante',
            nome='Usuario Existente',
            cpf='11122233344',
            email='duplicado@test.local',
            ra='RA-EXISTENTE',
            course_id=course.id,
        )
        existing.set_password('1234')
        db.session.add(existing)
        db.session.commit()

    _login_admin(client)
    csv_content = (
        "username,nome,email,cpf,ra,perfil,curso_nome,permitir_criar_eventos,senha\n"
        "legacy_ok,Usuario Legado,legacy_ok@test.local,98765432100,RA-LEGADO,coordenacao,Curso CSV Legado,1,senha-legado\n"
        "duplicate_email,Duplicado,duplicado@test.local,22233344455,RA-DUP,participante,Curso CSV Legado,0,\n"
        "invalid_role,Perfil Invalido,perfil@test.local,33344455566,RA-ROLE,invalido,Curso CSV Legado,0,\n"
        "missing_course,Curso Faltante,curso@test.local,44455566677,RA-CURSO,participante,Curso Inexistente,0,\n"
    )

    res = client.post(
        '/api/importar_usuarios_csv',
        data={'file': (BytesIO(csv_content.encode('utf-8')), 'usuarios_legado.csv')},
        content_type='multipart/form-data',
    )

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['importados'] == 1
    assert len(payload['erros']) == 3
    assert any('duplicado@test.local' in error.lower() and 'outro usuário' in error.lower() for error in payload['erros'])
    assert any('perfil inválido' in error.lower() and 'invalido' in error.lower() for error in payload['erros'])
    assert any('curso não encontrado' in error.lower() and 'curso inexistente' in error.lower() for error in payload['erros'])

    with app.app_context():
        imported = db.session.get(User, '98765432100')
        assert imported is not None
        assert imported.role == 'coordenador'
        assert imported.curso == 'Curso CSV Legado'
        assert imported.can_create_events is True
        assert imported.check_password('senha-legado') is True


def test_import_users_csv_updates_existing_user_by_cpf(client, app, admin_user):
    with app.app_context():
        old_course = Course(nome='Curso CSV Antigo')
        new_course = Course(nome='Curso CSV Atualizado')
        db.session.add_all([old_course, new_course])
        db.session.flush()

        existing = User(
            username='legacy_existing_user',
            role='participante',
            nome='Usuario Antigo',
            cpf='22233344455',
            email='old_csv@test.local',
            ra='RA-OLD',
            course_id=old_course.id,
            can_create_events=False,
        )
        existing.set_password('1234')
        db.session.add(existing)
        db.session.commit()

    _login_admin(client)
    csv_content = (
        "nome,email,cpf,ra,role,curso,can_create_events,password\n"
        "Usuario Atualizado,new_csv@test.local,222.333.444-55,RA-NEW,professor,Curso CSV Atualizado,sim,nova-senha\n"
    )

    res = client.post(
        '/api/importar_usuarios_csv',
        data={'file': (BytesIO(csv_content.encode('utf-8')), 'usuarios_update.csv')},
        content_type='multipart/form-data',
    )

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['importados'] == 1
    assert payload['created'] == 0
    assert payload['updated'] == 1
    assert payload['unchanged'] == 0
    assert payload['erros'] == []

    with app.app_context():
        updated = db.session.get(User, 'legacy_existing_user')
        assert updated is not None
        assert updated.nome == 'Usuario Atualizado'
        assert updated.email == 'new_csv@test.local'
        assert updated.ra == 'RA-NEW'
        assert updated.role == 'professor'
        assert updated.curso == 'Curso CSV Atualizado'
        assert updated.can_create_events is True
        assert updated.check_password('nova-senha') is True


def test_users_admin_page_reuses_rich_csv_import_flow(client, admin_user):
    _login_admin(client)

    res = client.get('/usuarios')

    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Importar Usuários (CSV)' in html
    assert '/api/importar_usuarios_csv/start' in html
    assert '/api/importar_usuarios_csv/status/${jobId}' in html
    assert 'Criadas' in html
    assert 'Atualizadas' in html


def test_mobile_first_management_pages_render_new_layout_markers(client, app, admin_user):
    event_id = _create_event_for_certs(app)

    with app.app_context():
        admin = db.session.get(User, 'admin_test')
        admin.can_create_events = True
        db.session.commit()

    _login_admin(client)

    create_res = client.get('/criar_evento')
    edit_res = client.get(f'/editar_evento/{event_id}')
    profile_res = client.get('/perfil')
    courses_res = client.get('/cursos')
    institutional_res = client.get('/certificados_institucionais')

    assert create_res.status_code == 200
    create_html = create_res.get_data(as_text=True)
    assert 'event-form-page' in create_html
    assert 'event-form-page__actions' in create_html
    assert 'event-form-page__map-actions' in create_html
    assert 'id="mainEventForm"' in create_html
    assert 'id="activitiesList"' in create_html

    assert edit_res.status_code == 200
    edit_html = edit_res.get_data(as_text=True)
    assert 'event-form-page' in edit_html
    assert 'event-form-page__breadcrumb' in edit_html
    assert 'event-form-page__subheader' in edit_html
    assert 'id="mainEventForm"' in edit_html

    assert profile_res.status_code == 200
    profile_html = profile_res.get_data(as_text=True)
    assert 'profile-page' in profile_html
    assert 'profile-page__hero' in profile_html
    assert 'profile-page__tabs' in profile_html
    assert 'id="profileTabs"' in profile_html
    assert 'id="tabela-atividades"' in profile_html

    assert courses_res.status_code == 200
    courses_html = courses_res.get_data(as_text=True)
    assert 'courses-admin-page' in courses_html
    assert 'courses-admin-page__filters' in courses_html
    assert 'courses-admin-page__table-shell' in courses_html
    assert 'id="tabelaCursos"' in courses_html

    assert institutional_res.status_code == 200
    institutional_html = institutional_res.get_data(as_text=True)
    assert 'institutional-certs-page' in institutional_html
    assert 'institutional-certs-page__table-shell' in institutional_html
    assert 'institutional-certs-modal' in institutional_html
    assert 'id="tabelaInstitucionais"' in institutional_html
    assert 'id="tabelaDestinatarios"' in institutional_html


def test_importar_usuarios_csv_start_and_status_update_existing_user(client, app, admin_user, monkeypatch):
    with app.app_context():
        course = Course(nome='Curso CSV Async')
        db.session.add(course)
        db.session.flush()

        existing = User(
            username='legacy_async_user',
            role='participante',
            nome='Usuario Async Antigo',
            cpf='99988877766',
            email='async_old@test.local',
            ra='RA-ASYNC-OLD',
            course_id=course.id,
            can_create_events=False,
        )
        existing.set_password('1234')
        db.session.add(existing)
        db.session.commit()

    class ImmediateThread:
        def __init__(self, target=None, args=None, daemon=None):
            self.target = target
            self.args = args or ()

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(admin_api, 'Thread', ImmediateThread)

    _login_admin(client)
    csv_content = (
        "nome,email,cpf,ra,role,curso,can_create_events,password\n"
        "Usuario Async Atualizado,async_new@test.local,999.888.777-66,RA-ASYNC-NEW,coordenacao,Curso CSV Async,1,senha-async\n"
        "Novo Usuario Async,new_async@test.local,123.123.123-12,RA-ASYNC-02,participante,Curso CSV Async,0,\n"
    )

    start_res = client.post(
        '/api/importar_usuarios_csv/start',
        data={'file': (BytesIO(csv_content.encode('utf-8')), 'usuarios_async.csv')},
        content_type='multipart/form-data',
    )

    assert start_res.status_code == 200
    start_payload = start_res.get_json()
    assert start_payload['job_id']
    assert start_payload['import_type'] == 'csv'

    status_res = client.get(f"/api/importar_usuarios_csv/status/{start_payload['job_id']}?page=1&per_page=10")

    assert status_res.status_code == 200
    payload = status_res.get_json()
    assert payload['completed'] is True
    assert payload['status'] == 'completed'
    assert payload['import_type'] == 'csv'
    assert payload['created'] == 1
    assert payload['updated'] == 1
    assert payload['unchanged'] == 0
    assert payload['errors_count'] == 0
    assert payload['pagination']['total_items'] == 2
    assert {row['status'] for row in payload['rows']} == {'created', 'updated'}

    with app.app_context():
        updated = db.session.get(User, 'legacy_async_user')
        created = db.session.get(User, '12312312312')

        assert updated is not None
        assert updated.nome == 'Usuario Async Atualizado'
        assert updated.email == 'async_new@test.local'
        assert updated.ra == 'RA-ASYNC-NEW'
        assert updated.role == 'coordenador'
        assert updated.can_create_events is True
        assert updated.check_password('senha-async') is True

        assert created is not None
        assert created.nome == 'Novo Usuario Async'
        assert created.role == 'participante'
        assert created.curso == 'Curso CSV Async'


def test_create_user_admin_endpoint_uses_cpf_as_username(client, admin_user):
    _login_admin(client)

    res = client.post('/api/criar_usuario', json={
        'username': 'nao-deve-ser-usado',
        'password': '1234',
        'nome': 'Criado via Admin',
        'email': 'criado_admin@test.local',
        'cpf': '555.444.333-22',
        'role': 'participante',
    })

    assert res.status_code == 200

    created_login = client.post('/api/login', json={'username': '55544433322', 'password': '1234'})
    assert created_login.status_code == 200


def test_create_event_api_rejects_user_without_flag_even_if_admin(client, admin_user):
    _login_admin(client)

    res = client.post('/api/criar_evento', json={
        'nome': 'API Event Blocked',
        'descricao': 'Via API',
        'is_rapido': True,
        'data_inicio': '2030-01-01',
        'hora_inicio': '10:00'
    })

    assert res.status_code == 403


def test_flagged_participant_can_access_event_creation_and_management(client, app, admin_user):
    seeded = _seed_flagged_event_creator(app)

    _login_user(client, seeded['username'])

    assert client.get('/criar_evento').status_code == 200
    assert client.get('/eventos_admin').status_code == 200

    res = client.post('/api/criar_evento', json={
        'nome': 'Evento Criado por Participante',
        'descricao': 'Criacao permitida pela flag.',
        'curso': seeded['course_name'],
        'is_rapido': True,
        'carga_horaria_rapida': 2,
        'data_inicio': '2030-02-01',
        'hora_inicio': '11:00'
    })

    assert res.status_code == 200
    with app.app_context():
        event = Event.query.filter_by(nome='Evento Criado por Participante').first()
        assert event is not None
        assert event.owner_username == seeded['username']
        assert event.course_id == seeded['course_id']


def test_dashboard_open_events_are_visible_and_enrollable_for_all_profiles(client, app, admin_user):
    seeded = _seed_open_events_access_data(app)

    for username in ['admin_test', *seeded['usernames']]:
        client.get('/logout')
        _login_user(client, username)
        html = client.get('/').get_data(as_text=True)
        assert 'Eventos em Aberto para Inscrição' in html
        assert 'filtPartTipo' in html
        assert 'filtPartSituacao' in html
        assert 'btnLimparFiltrosEventosAbertos' in html

    client.get('/logout')
    _login_user(client, 'open_extensao')

    open_events_res = client.get('/api/eventos_abertos')
    assert open_events_res.status_code == 200
    payload = open_events_res.get_json()
    assert [item['nome'] for item in payload['items']] == [seeded['open_event_name']]

    enrollment_res = client.post('/api/toggle_inscricao', json={
        'activity_id': seeded['open_activity_id'],
        'acao': 'inscrever',
    })
    assert enrollment_res.status_code == 200

    with app.app_context():
        enrollment = Enrollment.query.filter_by(
            activity_id=seeded['open_activity_id'],
            user_cpf=seeded['open_extensao_cpf'],
        ).first()
        assert enrollment is not None

def test_create_event_api(client, app, admin_user):
    with app.app_context():
        admin = db.session.get(User, 'admin_test')
        admin.can_create_events = True
        db.session.commit()

    client.post('/api/login', json={'username': 'admin_test', 'password': '1234'})
    
    data = {
        'nome': 'API Event',
        'descricao': 'Via API',
        'is_rapido': True,
        'carga_horaria_rapida': 2,
        'data_inicio': '2030-01-01',
        'hora_inicio': '10:00'
    }
    res = client.post('/api/criar_evento', json=data)
    assert res.status_code == 200
    assert 'link' in res.json


def test_create_standard_event_api_returns_multiple_speakers_and_legacy_fields(client, app, admin_user):
    with app.app_context():
        admin = db.session.get(User, 'admin_test')
        admin.can_create_events = True
        db.session.commit()

    _login_admin(client)
    data = {
        'nome': 'Evento API com Contato',
        'descricao': 'Via API com multiplos palestrantes',
        'is_rapido': False,
        'data_inicio': '2030-04-10',
        'hora_inicio': '18:00',
        'data_fim': '2030-04-10',
        'hora_fim': '22:00',
        'atividades': [
            {
                'nome': 'Palestra de Abertura',
                'palestrantes': [
                    {'nome': 'Dra. API', 'email': 'dra.api@example.com', 'ordem': 0},
                    {'nome': 'Dr. Convidado', 'email': 'dr.convidado@example.com', 'ordem': 1},
                ],
                'local': 'Auditorio Central',
                'descricao': 'Apresentacao principal',
                'data_atv': '2030-04-10',
                'hora_atv': '19:00',
                'horas': 2,
                'vagas': 120,
            }
        ],
    }

    res = client.post('/api/criar_evento', json=data)
    assert res.status_code == 200

    list_res = client.get('/api/eventos')
    assert list_res.status_code == 200
    payload = list_res.get_json()
    activity = payload['items'][0]['atividades'][0]
    assert activity['palestrante'] == 'Dra. API'
    assert activity['email_palestrante'] == 'dra.api@example.com'
    assert activity['palestrantes_label'] == 'Dra. API, Dr. Convidado'
    assert [speaker['nome'] for speaker in activity['palestrantes']] == ['Dra. API', 'Dr. Convidado']
    assert activity['palestrantes'][0]['email'] == 'dra.api@example.com'

    with app.app_context():
        saved_event = Event.query.filter_by(nome='Evento API com Contato').first()
        assert saved_event is not None
        saved_activity = Activity.query.filter_by(event_id=saved_event.id, nome='Palestra de Abertura').first()
        assert saved_activity is not None
        assert len(saved_activity.speakers) == 2
        assert saved_activity.speakers[0].nome == 'Dra. API'
        assert saved_activity.email_palestrante == 'dra.api@example.com'


def test_open_events_api_hides_speaker_emails_for_participant(client, app, admin_user):
    with app.app_context():
        admin = db.session.get(User, 'admin_test')
        admin.can_create_events = True
        participant = User(
            username='open_events_participant',
            role='participante',
            nome='Participante Eventos',
            cpf='11122233344',
            email='open_events_participant@test.local',
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.commit()

    _login_admin(client)
    res = client.post('/api/criar_evento', json={
        'nome': 'Evento Aberto com Palestrantes',
        'descricao': 'Evento para validar exposicao publica',
        'is_rapido': False,
        'data_inicio': '2030-04-11',
        'hora_inicio': '18:00',
        'data_fim': '2030-04-11',
        'hora_fim': '22:00',
        'atividades': [
            {
                'nome': 'Mesa Publica',
                'palestrantes': [
                    {'nome': 'Dra. API', 'email': 'dra.api@example.com', 'ordem': 0},
                    {'nome': 'Dr. Convidado', 'email': 'dr.convidado@example.com', 'ordem': 1},
                ],
                'local': 'Auditorio',
                'descricao': 'Mesa principal',
                'data_atv': '2030-04-11',
                'hora_atv': '19:00',
                'horas': 2,
                'vagas': 120,
            }
        ],
    })
    assert res.status_code == 200

    client.get('/api/logout')
    _login_user(client, 'open_events_participant')
    list_res = client.get('/api/eventos_abertos')

    assert list_res.status_code == 200
    payload = list_res.get_json()
    activity = payload['items'][0]['atividades'][0]
    assert activity['palestrantes_label'] == 'Dra. API, Dr. Convidado'
    assert activity['palestrantes'][0]['email'] is None
    assert activity['palestrantes'][1]['email'] is None


def test_open_events_api_supports_extended_filters_and_keeps_course_name_compatibility(client, app, admin_user):
    seeded = _seed_open_events_filter_data(app)

    _login_user(client, seeded['participant_username'])

    by_course_id = client.get(f"/api/eventos_abertos?course_id={seeded['course_tech_id']}")
    assert by_course_id.status_code == 200
    assert [item['nome'] for item in by_course_id.get_json()['items']] == [seeded['python_event_name']]

    by_course_name = client.get(f"/api/eventos_abertos?curso=Tecnologia")
    assert by_course_name.status_code == 200
    assert [item['nome'] for item in by_course_name.get_json()['items']] == [seeded['python_event_name']]

    by_type = client.get('/api/eventos_abertos?tipo=RAPIDO')
    assert by_type.status_code == 200
    assert [item['nome'] for item in by_type.get_json()['items']] == [seeded['law_event_name']]

    by_programming = client.get('/api/eventos_abertos?programacao=Maria')
    assert by_programming.status_code == 200
    assert [item['nome'] for item in by_programming.get_json()['items']] == [seeded['python_event_name']]

    by_period = client.get('/api/eventos_abertos?data_inicio=2030-09-01&data_fim=2030-09-15')
    assert by_period.status_code == 200
    assert [item['nome'] for item in by_period.get_json()['items']] == [seeded['python_event_name']]


def test_open_events_api_can_filter_by_current_user_enrollment_status(client, app, admin_user):
    seeded = _seed_open_events_filter_data(app)

    _login_user(client, seeded['participant_username'])

    enrolled = client.get('/api/eventos_abertos?situacao=inscrito')
    assert enrolled.status_code == 200
    assert [item['nome'] for item in enrolled.get_json()['items']] == [seeded['python_event_name']]

    not_enrolled = client.get('/api/eventos_abertos?situacao=nao_inscrito')
    assert not_enrolled.status_code == 200
    assert [item['nome'] for item in not_enrolled.get_json()['items']] == [seeded['law_event_name']]


def test_open_events_api_respects_allowed_roles_and_exposes_registration_categories(client, app, admin_user):
    with app.app_context():
        professor = User(
            username='allowed_role_professor',
            role='professor',
            nome='Professor Perfil',
            cpf='30040050060',
        )
        professor.set_password('1234')
        participant = User(
            username='blocked_role_participant',
            role='participante',
            nome='Participante Bloqueado',
            cpf='30040050061',
        )
        participant.set_password('1234')
        db.session.add_all([professor, participant])
        db.session.commit()

        service = EventService()
        event = service.create_event(admin_user.username, {
            'nome': 'Evento Restrito a Docentes',
            'descricao': 'Evento com inscricao por perfil',
            'is_rapido': False,
            'data_inicio': '2030-09-20',
            'hora_inicio': '18:00',
            'data_fim': '2030-09-20',
            'hora_fim': '21:00',
            'perfis_habilitados': ['professor'],
            'categorias_inscricao': [
                {'nome': 'Docente', 'vagas': 2},
                {'nome': 'Ouvinte', 'vagas': -1},
            ],
            'atividades': [
                {
                    'nome': 'Mesa Docente',
                    'local': 'Auditorio',
                    'descricao': 'Atividade principal',
                    'data_atv': '2030-09-20',
                    'hora_atv': '18:30',
                    'horas': 2,
                    'vagas': 30,
                }
            ],
        })
        event_name = event.nome

    _login_user(client, 'blocked_role_participant')
    blocked_res = client.get('/api/eventos_abertos')
    assert blocked_res.status_code == 200
    assert [item['nome'] for item in blocked_res.get_json()['items']] == []

    client.get('/api/logout')
    _login_user(client, 'allowed_role_professor')
    allowed_res = client.get('/api/eventos_abertos')
    assert allowed_res.status_code == 200
    payload = allowed_res.get_json()
    assert [item['nome'] for item in payload['items']] == [event_name]
    event_payload = payload['items'][0]
    assert event_payload['perfis_habilitados'] == ['professor']
    assert [item['nome'] for item in event_payload['categorias_inscricao']] == ['Docente', 'Ouvinte']
    assert event_payload['pode_se_inscrever'] is True


def test_toggle_inscricao_api_reuses_existing_event_category(client, app, admin_user):
    with app.app_context():
        participant = User(
            username='toggle_category_participant',
            role='participante',
            nome='Participante Categoria API',
            cpf='30040050062',
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.commit()

        service = EventService()
        event = service.create_event(admin_user.username, {
            'nome': 'Evento API Categoria',
            'descricao': 'Evento com duas atividades',
            'is_rapido': False,
            'data_inicio': '2030-10-10',
            'hora_inicio': '18:00',
            'data_fim': '2030-10-10',
            'hora_fim': '22:00',
            'perfis_habilitados': ['participante'],
            'categorias_inscricao': [
                {'nome': 'Aluno', 'vagas': 3},
                {'nome': 'Ouvinte', 'vagas': 3},
            ],
            'atividades': [
                {
                    'nome': 'Atividade 1',
                    'local': 'Sala 1',
                    'descricao': 'Primeira',
                    'data_atv': '2030-10-10',
                    'hora_atv': '18:30',
                    'horas': 2,
                    'vagas': 20,
                },
                {
                    'nome': 'Atividade 2',
                    'local': 'Sala 2',
                    'descricao': 'Segunda',
                    'data_atv': '2030-10-10',
                    'hora_atv': '20:00',
                    'horas': 2,
                    'vagas': 20,
                },
            ],
        })
        categories = {category.nome: category.id for category in event.registration_categories}
        activity_ids = [activity.id for activity in sorted(event.activities, key=lambda activity: activity.id)]
        participant_cpf = participant.cpf

    _login_user(client, 'toggle_category_participant')

    first_res = client.post('/api/toggle_inscricao', json={
        'activity_id': activity_ids[0],
        'acao': 'inscrever',
        'categoria_inscricao_id': categories['Aluno'],
    })
    assert first_res.status_code == 200
    assert first_res.get_json()['categoria_inscricao']['nome'] == 'Aluno'
    assert first_res.get_json()['possui_inscricao_evento'] is True

    second_res = client.post('/api/toggle_inscricao', json={
        'activity_id': activity_ids[1],
        'acao': 'inscrever',
        'categoria_inscricao_id': categories['Ouvinte'],
    })
    assert second_res.status_code == 200
    assert second_res.get_json()['categoria_inscricao']['nome'] == 'Aluno'
    assert second_res.get_json()['possui_inscricao_evento'] is True

    with app.app_context():
        enrollments = Enrollment.query.filter_by(user_cpf=participant_cpf).order_by(Enrollment.activity_id).all()
        assert len(enrollments) == 2
        assert enrollments[0].event_registration_id == enrollments[1].event_registration_id


def test_manual_enroll_api_and_reports_include_registration_category(client, app, admin_user):
    with app.app_context():
        participant = User(
            username='manual_category_user',
            role='participante',
            nome='Participante Manual Categoria',
            cpf='30040050063',
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.commit()

        service = EventService()
        event = service.create_event(admin_user.username, {
            'nome': 'Evento Manual Categoria',
            'descricao': 'Evento para relatorios',
            'is_rapido': False,
            'data_inicio': '2030-11-05',
            'hora_inicio': '18:00',
            'data_fim': '2030-11-05',
            'hora_fim': '20:00',
            'perfis_habilitados': ['participante'],
            'categorias_inscricao': [
                {'nome': 'Aluno', 'vagas': 5},
                {'nome': 'Ouvinte', 'vagas': 5},
            ],
            'atividades': [
                {
                    'nome': 'Atividade Manual',
                    'local': 'Sala Manual',
                    'descricao': 'Atividade',
                    'data_atv': '2030-11-05',
                    'hora_atv': '18:30',
                    'horas': 2,
                    'vagas': 20,
                }
            ],
        })
        event_id = event.id
        activity_id = event.activities[0].id
        category_id = next(category.id for category in event.registration_categories if category.nome == 'Aluno')
        participant_cpf = participant.cpf

    _login_admin(client)
    enroll_res = client.post('/api/inscricao_manual', json={
        'cpf': participant_cpf,
        'activity_id': activity_id,
        'categoria_inscricao_id': category_id,
    })
    assert enroll_res.status_code == 200

    participants_res = client.get(f'/api/participantes_evento/{event_id}')
    assert participants_res.status_code == 200
    assert participants_res.get_json()['items'][0]['categoria_inscricao'] == 'Aluno'

    report_res = client.get(f'/api/relatorio_inscritos/{event_id}')
    assert report_res.status_code == 200
    assert report_res.get_json()['items'][0]['categoria_inscricao'] == 'Aluno'


def test_manual_enroll_api_sends_email_notification(client, app, admin_user, monkeypatch):
    seeded = _seed_manual_enrollment_data(app)
    sent_payloads = []
    monkeypatch.setattr(
        admin_api.admin_service.notification_service,
        'send_email_task',
        lambda **kwargs: sent_payloads.append(kwargs) or True
    )

    _login_admin(client)
    res = client.post('/api/inscricao_manual', json={
        'cpf': seeded['cpf'],
        'activity_id': seeded['activity_id'],
    })

    assert res.status_code == 200
    assert res.get_json()['mensagem'] == 'Inscrição realizada com sucesso.'
    assert len(sent_payloads) == 1
    assert sent_payloads[0]['template_name'] == 'manual_enrollment_confirmation.html'
    assert sent_payloads[0]['subject'] == 'Você foi adicionado ao evento: Evento API Manual'

    with app.app_context():
        enrollment = Enrollment.query.filter_by(user_cpf=seeded['cpf'], activity_id=seeded['activity_id']).first()
        assert enrollment is not None
        assert enrollment.presente is True


def test_manual_enroll_api_allows_extensao_in_event_management(client, app, admin_user, monkeypatch):
    seeded = _seed_manual_enrollment_data(app)
    sent_payloads = []
    monkeypatch.setattr(
        admin_api.admin_service.notification_service,
        'send_email_task',
        lambda **kwargs: sent_payloads.append(kwargs) or True
    )

    _login_user(client, seeded['extension_username'])

    search_res = client.get('/api/buscar_participante?q=Participante')
    res = client.post('/api/inscricao_manual', json={
        'cpf': seeded['cpf'],
        'activity_id': seeded['activity_id'],
    })

    assert search_res.status_code == 200
    assert any(item['cpf'] == seeded['cpf'] for item in search_res.get_json())
    assert res.status_code == 200
    assert res.get_json()['mensagem'] == 'Inscrição realizada com sucesso.'
    assert len(sent_payloads) == 1

    with app.app_context():
        enrollment = Enrollment.query.filter_by(user_cpf=seeded['cpf'], activity_id=seeded['activity_id']).first()
        assert enrollment is not None
        assert enrollment.presente is True


def test_manual_enroll_api_duplicate_does_not_send_email(client, app, admin_user, monkeypatch):
    seeded = _seed_manual_enrollment_data(app)
    with app.app_context():
        db.session.add(Enrollment(
            activity_id=seeded['activity_id'],
            user_cpf=seeded['cpf'],
            nome=seeded['participant_name'],
            presente=True,
        ))
        db.session.commit()

    sent_payloads = []
    monkeypatch.setattr(
        admin_api.admin_service.notification_service,
        'send_email_task',
        lambda **kwargs: sent_payloads.append(kwargs) or True
    )

    _login_admin(client)
    res = client.post('/api/inscricao_manual', json={
        'cpf': seeded['cpf'],
        'activity_id': seeded['activity_id'],
    })

    assert res.status_code == 400
    assert res.get_json()['erro'] == 'Usuário já está inscrito nesta atividade.'
    assert sent_payloads == []


def test_manual_enroll_api_invalid_activity_does_not_send_email(client, app, admin_user, monkeypatch):
    seeded = _seed_manual_enrollment_data(app)
    sent_payloads = []
    monkeypatch.setattr(
        admin_api.admin_service.notification_service,
        'send_email_task',
        lambda **kwargs: sent_payloads.append(kwargs) or True
    )

    _login_admin(client)
    res = client.post('/api/inscricao_manual', json={
        'cpf': seeded['cpf'],
        'activity_id': 'invalido',
    })

    assert res.status_code == 400
    assert res.get_json()['erro'] == 'Atividade inválida.'
    assert sent_payloads == []


def test_certificate_setup_rejects_invalid_json(client, app, admin_user):
    _login_admin(client)
    event_id = _create_event_for_certs(app)

    data = {
        'template': '{"broken": true'
    }
    res = client.post(f'/api/certificates/setup/{event_id}', data=data)
    assert res.status_code == 400
    assert 'Template inválido' in res.json['erro']


def test_certificate_setup_accepts_v2_template(client, app, admin_user):
    _login_admin(client)
    event_id = _create_event_for_certs(app)

    payload = {
        'version': 2,
        'document': {'gridSize': 2, 'snap': True, 'guides': True},
        'elements': [
            {
                'id': 'txt1',
                'type': 'text',
                'text': 'CERTIFICADO {{NOME}}',
                'x': 50,
                'y': 20,
                'w': 80,
                'h': 10,
                'font': 30,
                'color': '#111111',
                'align': 'center',
                'font_family': 'Helvetica',
                'zIndex': 1,
                'locked': False,
                'visible': True
            }
        ]
    }
    res = client.post(
        f'/api/certificates/setup/{event_id}',
        data={'template': json.dumps(payload)}
    )

    assert res.status_code == 200
    with app.app_context():
        event = db.session.get(Event, event_id)
        saved = json.loads(event.cert_template_json)
        assert saved['version'] == 2
        assert saved['elements'][0]['id'] == 'txt1'


def test_certificate_setup_normalizes_fonts_and_injects_required_elements(client, app, admin_user):
    _login_admin(client)
    event_id = _create_event_for_certs(app)

    payload = {
        'version': 2,
        'document': {'gridSize': 2, 'snap': True, 'guides': True},
        'elements': [
            {
                'id': 'txt1',
                'type': 'text',
                'text': 'CERTIFICADO {{NOME}}',
                'x': 50,
                'y': 20,
                'w': 80,
                'h': 10,
                'font': 30,
                'color': '#111111',
                'align': 'center',
                'font_family': 'Arial',
                'zIndex': 1,
                'locked': False,
                'visible': True
            }
        ]
    }

    res = client.post(
        f'/api/certificates/setup/{event_id}',
        data={'template': json.dumps(payload)}
    )

    assert res.status_code == 200
    with app.app_context():
        event = db.session.get(Event, event_id)
        saved = json.loads(event.cert_template_json)
        txt1 = next(item for item in saved['elements'] if item['id'] == 'txt1')
        date_fixed = next(item for item in saved['elements'] if item['id'] == 'date_fixed')
        fixed_ids = {item['id'] for item in saved['elements']}

        assert txt1['font_family'] == 'Helvetica'
        assert '{{DATA}}' in date_fixed['text']
        assert {'name_fixed', 'date_fixed', 'hash', 'qrcode'}.issubset(fixed_ids)


def test_certificate_designer_default_script_removes_participation_title(client, app, admin_user):
    _login_admin(client)
    event_id = _create_event_for_certs(app)

    res = client.get(f'/designer_certificado/{event_id}')

    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'CERTIFICADO DE PARTICIPAÇÃO' not in html


def test_certificate_preview_layout_returns_pdf(client, app, admin_user):
    _login_admin(client)
    event_id = _create_event_for_certs(app)

    payload = {
        'template': {
            'version': 2,
            'document': {'gridSize': 2, 'snap': True, 'guides': True},
            'elements': [
                {
                    'id': 'txt2',
                    'type': 'text',
                    'text': 'Certificamos que {{NOME}} participou do evento {{EVENTO}} em {{DATA}}.',
                    'x': 50,
                    'y': 50,
                    'w': 70,
                    'h': 15,
                    'font': 22,
                    'color': '#111111',
                    'align': 'center',
                    'font_family': 'Helvetica',
                    'visible': True,
                }
            ],
        },
        'preview_data': {
            '{{NOME}}': 'Participante Preview',
            '{{CPF}}': '123.456.789-00',
            '{{EVENTO}}': 'Evento Preview',
            '{{HORAS}}': '4 horas',
            '{{DATA}}': '15/03/2026',
            '{{HASH}}': 'PREVIEWHASH0001',
        },
    }

    res = client.post(f'/api/certificates/preview_layout/{event_id}', json=payload)

    assert res.status_code == 200
    assert res.mimetype == 'application/pdf'
    assert res.data.startswith(b'%PDF')


def test_institutional_certificate_preview_layout_returns_pdf(client, app, admin_user):
    with app.app_context():
        category = InstitutionalCertificateCategory(nome='Reconhecimento')
        db.session.add(category)
        db.session.flush()

        cert = InstitutionalCertificate(
            created_by_username='admin_test',
            titulo='Certificado Institucional Preview',
            category_id=category.id,
            descricao='Teste',
            data_emissao='2030-01-10',
            signer_name='Coord. NUTED',
        )
        db.session.add(cert)
        db.session.commit()
        certificate_id = cert.id

    _login_admin(client)
    payload = {
        'template': {
            'version': 2,
            'document': {'gridSize': 2, 'snap': True, 'guides': True},
            'elements': [
                {
                    'id': 'txt2',
                    'type': 'text',
                    'text': 'Certificamos que {{RECIPIENT_NAME}} participou de {{CERTIFICATE_TITLE}}.',
                    'x': 50,
                    'y': 50,
                    'w': 70,
                    'h': 15,
                    'font': 22,
                    'color': '#111111',
                    'align': 'center',
                    'font_family': 'Helvetica',
                    'visible': True,
                }
            ],
        },
        'preview_data': {
            '{{RECIPIENT_NAME}}': 'Destinatário Preview',
            '{{CERTIFICATE_TITLE}}': 'Certificado Institucional Preview',
            '{{CATEGORY}}': 'Reconhecimento',
            '{{CARGA_HORARIA}}': '12 horas',
            '{{CURSO_USUARIO}}': 'Direito',
            '{{EMISSION_DATE}}': '15/03/2026',
            '{{SIGNER}}': 'Coord. NUTED',
            '{{CPF}}': '123.456.789-00',
            '{{HASH}}': 'INSTPREVHASH001',
        },
    }

    res = client.post(f'/api/institutional_certificates/{certificate_id}/preview_layout', json=payload)

    assert res.status_code == 200
    assert res.mimetype == 'application/pdf'
    assert res.data.startswith(b'%PDF')


def test_create_institutional_certificate_persists_default_template_when_missing(client, app, admin_user):
    _login_admin(client)

    res = client.post('/api/institutional_certificates', json={
        'titulo': 'Certificado Institucional Base',
        'categoria': 'Reconhecimento',
        'data_emissao': '2030-01-10',
    })

    assert res.status_code == 201
    certificate_id = res.json['id']

    with app.app_context():
        cert = db.session.get(InstitutionalCertificate, certificate_id)
        saved = json.loads(cert.cert_template_json)
        by_id = {item['id']: item for item in saved['elements']}

        assert {'txt2', 'name_fixed', 'date_fixed', 'hash', 'qrcode'}.issubset(by_id.keys())
        assert by_id['txt2']['text'] == 'Certificamos que {{RECIPIENT_NAME}} participou como {{CATEGORY}} do curso {{CURSO_USUARIO}}, com carga horária de {{CARGA_HORARIA}} horas.'


def test_institutional_certificates_keep_gestor_read_only_for_foreign_records(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    with app.app_context():
        cert = InstitutionalCertificate.query.filter_by(created_by_username=seeded['prof_eng_a_username']).first()
        assert cert is not None
        cert_id = cert.id

    _login_user(client, seeded['gestor_username'])

    list_res = client.get('/api/institutional_certificates')
    assert list_res.status_code == 200
    payload = list_res.get_json()
    assert payload['total'] == 3
    assert all(item['can_edit'] is False for item in payload['items'])

    detail_res = client.get(f'/api/institutional_certificates/{cert_id}')
    assert detail_res.status_code == 200
    assert detail_res.get_json()['can_edit'] is False

    update_res = client.put(f'/api/institutional_certificates/{cert_id}', json={})
    designer_res = client.get(f'/designer_certificado_institucional/{cert_id}')

    assert update_res.status_code == 403
    assert designer_res.status_code == 403


def test_institutional_certificates_allow_extensao_edit_but_only_delete_own_records(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    with app.app_context():
        editable_cert = InstitutionalCertificate.query.filter_by(created_by_username=seeded['prof_eng_a_username']).first()
        foreign_cert = InstitutionalCertificate.query.filter_by(created_by_username=seeded['prof_eng_b_username']).first()
        assert editable_cert is not None
        assert foreign_cert is not None

        own_cert = InstitutionalCertificate(
            created_by_username=seeded['extensao_username'],
            titulo='Certificado Extensao',
            category_id=editable_cert.category_id,
            descricao='Lote institucional Extensao',
            data_emissao=date.today().isoformat(),
            signer_name='Coord. Extensao',
            status='RASCUNHO',
        )
        db.session.add(own_cert)
        db.session.commit()

        editable_cert_id = editable_cert.id
        foreign_cert_id = foreign_cert.id
        own_cert_id = own_cert.id

    _login_user(client, seeded['extensao_username'])

    list_res = client.get('/api/institutional_certificates')
    assert list_res.status_code == 200
    payload = list_res.get_json()
    assert payload['total'] == 4
    assert all(item['can_edit'] is True for item in payload['items'])
    can_delete_by_id = {item['id']: item['can_delete'] for item in payload['items']}
    assert can_delete_by_id[editable_cert_id] is False
    assert can_delete_by_id[foreign_cert_id] is False
    assert can_delete_by_id[own_cert_id] is True

    detail_res = client.get(f'/api/institutional_certificates/{foreign_cert_id}')
    assert detail_res.status_code == 200
    assert detail_res.get_json()['can_edit'] is True
    assert detail_res.get_json()['can_delete'] is False

    designer_res = client.get(f'/designer_certificado_institucional/{editable_cert_id}')
    update_res = client.put(f'/api/institutional_certificates/{editable_cert_id}', json={
        'titulo': 'Certificado Engenharia A - Ajustado',
        'categoria': 'Extensao',
        'data_emissao': date.today().isoformat(),
        'status': 'ENVIADO',
        'descricao': 'Atualizado pela extensao',
        'signer_name': 'Coord. Extensao',
    })
    delete_foreign_res = client.delete(f'/api/institutional_certificates/{foreign_cert_id}')
    delete_own_res = client.delete(f'/api/institutional_certificates/{own_cert_id}')

    assert designer_res.status_code == 200
    assert update_res.status_code == 200
    assert delete_foreign_res.status_code == 403
    assert delete_own_res.status_code == 200

    with app.app_context():
        updated_cert = db.session.get(InstitutionalCertificate, editable_cert_id)
        preserved_foreign_cert = db.session.get(InstitutionalCertificate, foreign_cert_id)
        deleted_own_cert = db.session.get(InstitutionalCertificate, own_cert_id)
        assert updated_cert.titulo == 'Certificado Engenharia A - Ajustado'
        assert preserved_foreign_cert is not None
        assert deleted_own_cert is None


def test_institutional_certificates_block_delete_when_any_recipient_exists(client, app, admin_user):
    with app.app_context():
        category = InstitutionalCertificateCategory(nome='Bloqueio Exclusao')
        db.session.add(category)
        db.session.flush()

        pending_cert = InstitutionalCertificate(
            created_by_username='admin_test',
            titulo='Certificado Com Destinatario Pendente',
            category_id=category.id,
            descricao='Nao deve ser excluido',
            data_emissao=date.today().isoformat(),
            signer_name='Coord. Admin',
            status='RASCUNHO',
        )
        delivered_cert = InstitutionalCertificate(
            created_by_username='admin_test',
            titulo='Certificado Com Destinatario Enviado',
            category_id=category.id,
            descricao='Nao deve ser excluido',
            data_emissao=date.today().isoformat(),
            signer_name='Coord. Admin',
            status='ENVIADO',
        )
        db.session.add_all([pending_cert, delivered_cert])
        db.session.flush()

        db.session.add_all([
            InstitutionalCertificateRecipient(
                certificate_id=pending_cert.id,
                nome='Aluno Pendente',
                email='pending_delete@test.local',
                cpf='40050060070',
                cert_hash='PENDINGBLOCK001',
                cert_entregue=False,
            ),
            InstitutionalCertificateRecipient(
                certificate_id=delivered_cert.id,
                nome='Aluno Enviado',
                email='delivered_delete@test.local',
                cpf='40050060071',
                cert_hash='DELIVERBLOCK001',
                cert_entregue=True,
            ),
        ])
        db.session.commit()
        pending_cert_id = pending_cert.id
        delivered_cert_id = delivered_cert.id

    _login_admin(client)

    list_res = client.get('/api/institutional_certificates')
    assert list_res.status_code == 200
    payload = list_res.get_json()
    by_id = {item['id']: item for item in payload['items']}
    assert by_id[pending_cert_id]['can_delete'] is False
    assert by_id[pending_cert_id]['can_delete_permission'] is True
    assert by_id[pending_cert_id]['linked_recipients_count'] == 1
    assert by_id[pending_cert_id]['has_linked_records'] is True
    assert by_id[pending_cert_id]['delete_block_reason'] == 'Não é possível excluir o certificado porque existem destinatários vinculados.'
    assert by_id[delivered_cert_id]['can_delete'] is False
    assert by_id[delivered_cert_id]['linked_recipients_count'] == 1
    assert by_id[delivered_cert_id]['has_linked_records'] is True

    detail_res = client.get(f'/api/institutional_certificates/{pending_cert_id}')
    assert detail_res.status_code == 200
    detail_payload = detail_res.get_json()
    assert detail_payload['can_delete'] is False
    assert detail_payload['can_delete_permission'] is True
    assert detail_payload['linked_recipients_count'] == 1
    assert detail_payload['has_linked_records'] is True
    assert detail_payload['delete_block_reason'] == 'Não é possível excluir o certificado porque existem destinatários vinculados.'

    delete_pending_res = client.delete(f'/api/institutional_certificates/{pending_cert_id}')
    delete_delivered_res = client.delete(f'/api/institutional_certificates/{delivered_cert_id}')
    assert delete_pending_res.status_code == 400
    assert delete_pending_res.get_json() == {
        'erro': 'Não é possível excluir o certificado porque existem destinatários vinculados.',
        'linked_recipients_count': 1,
    }
    assert delete_delivered_res.status_code == 400
    assert delete_delivered_res.get_json() == {
        'erro': 'Não é possível excluir o certificado porque existem destinatários vinculados.',
        'linked_recipients_count': 1,
    }

    with app.app_context():
        assert db.session.get(InstitutionalCertificate, pending_cert_id) is not None
        assert db.session.get(InstitutionalCertificate, delivered_cert_id) is not None


def test_institutional_certificates_allow_coordinator_read_only_only_for_own_course(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    with app.app_context():
        cert_eng_a = InstitutionalCertificate.query.filter_by(created_by_username=seeded['prof_eng_a_username']).first()
        cert_eng_b = InstitutionalCertificate.query.filter_by(created_by_username=seeded['prof_eng_b_username']).first()
        cert_dir = InstitutionalCertificate.query.filter_by(created_by_username='prof_dir').first()
        assert cert_eng_a is not None
        assert cert_eng_b is not None
        assert cert_dir is not None

        eng_recipient = InstitutionalCertificateRecipient.query.filter_by(
            certificate_id=cert_eng_a.id,
            user_username='student_eng_a',
        ).first()
        mixed_recipient = InstitutionalCertificateRecipient.query.filter_by(
            certificate_id=cert_eng_a.id,
            user_username='student_dir',
        ).first()
        assert eng_recipient is not None
        assert mixed_recipient is not None

        cert_eng_a_id = cert_eng_a.id
        cert_eng_b_id = cert_eng_b.id
        cert_dir_id = cert_dir.id
        eng_recipient_id = eng_recipient.id
        mixed_recipient_id = mixed_recipient.id

    _login_user(client, seeded['coord_username'])

    page_res = client.get('/certificados_institucionais')
    list_res = client.get('/api/institutional_certificates')
    detail_allowed_res = client.get(f'/api/institutional_certificates/{cert_eng_a_id}')
    detail_denied_res = client.get(f'/api/institutional_certificates/{cert_dir_id}')
    recipients_res = client.get(f'/api/institutional_certificates/{cert_eng_a_id}/recipients')
    export_res = client.get(f'/api/institutional_certificates/{cert_eng_a_id}/recipients/export_csv')
    designer_res = client.get(f'/designer_certificado_institucional/{cert_eng_a_id}')
    denied_designer_res = client.get(f'/designer_certificado_institucional/{cert_dir_id}')
    preview_layout_res = client.post(f'/api/institutional_certificates/{cert_eng_a_id}/preview_layout', json={
        'template': {
            'version': 2,
            'document': {'gridSize': 2, 'snap': True, 'guides': True},
            'elements': [
                {
                    'id': 'txt1',
                    'type': 'text',
                    'text': 'Certificamos {{RECIPIENT_NAME}} em {{CURSO_USUARIO}}.',
                    'x': 50,
                    'y': 50,
                    'w': 70,
                    'h': 15,
                    'font': 22,
                    'color': '#111111',
                    'align': 'center',
                    'font_family': 'Helvetica',
                    'visible': True,
                }
            ],
        },
        'preview_data': {
            '{{RECIPIENT_NAME}}': 'Aluno Eng A',
            '{{CERTIFICATE_TITLE}}': 'Certificado Engenharia A',
            '{{CATEGORY}}': 'Extensao',
            '{{CARGA_HORARIA}}': '4',
            '{{CURSO_USUARIO}}': 'Engenharia',
            '{{EMISSION_DATE}}': '15/03/2026',
            '{{SIGNER}}': 'Coord. Eng A',
            '{{CPF}}': '20030040057',
            '{{HASH}}': 'COORDENGPREVIEW',
        },
    })
    update_res = client.put(f'/api/institutional_certificates/{cert_eng_a_id}', json={})
    preview_allowed_res = client.get(
        f'/api/institutional_certificates/{cert_eng_a_id}/recipients/{eng_recipient_id}/preview'
    )
    preview_denied_res = client.get(
        f'/api/institutional_certificates/{cert_eng_a_id}/recipients/{mixed_recipient_id}/preview'
    )

    assert page_res.status_code == 200

    assert list_res.status_code == 200
    payload = list_res.get_json()
    assert payload['total'] == 2
    assert {item['id'] for item in payload['items']} == {cert_eng_a_id, cert_eng_b_id}
    assert all(item['can_edit'] is False for item in payload['items'])
    assert all(item['can_delete'] is False for item in payload['items'])
    assert all(item['can_view_designer'] is True for item in payload['items'])
    recipients_count_by_id = {item['id']: item['recipients_count'] for item in payload['items']}
    assert recipients_count_by_id[cert_eng_a_id] == 1
    assert recipients_count_by_id[cert_eng_b_id] == 1

    assert detail_allowed_res.status_code == 200
    detail_payload = detail_allowed_res.get_json()
    assert detail_payload['can_edit'] is False
    assert detail_payload['can_delete'] is False
    assert detail_payload['can_view_designer'] is True
    assert detail_payload['recipients_count'] == 1

    assert detail_denied_res.status_code == 403

    assert recipients_res.status_code == 200
    recipients_payload = recipients_res.get_json()
    assert recipients_payload['total'] == 1
    assert [item['user_username'] for item in recipients_payload['items']] == ['student_eng_a']

    assert export_res.status_code == 200
    export_text = export_res.data.decode('utf-8')
    assert 'eng_a@test.local' in export_text
    assert 'dir_mix@test.local' not in export_text

    assert designer_res.status_code == 200
    assert denied_designer_res.status_code == 403
    assert preview_layout_res.status_code == 200
    assert preview_layout_res.mimetype == 'application/pdf'
    assert update_res.status_code == 403

    assert preview_allowed_res.status_code == 200
    assert preview_allowed_res.mimetype == 'application/pdf'
    assert preview_denied_res.status_code == 404


def test_institutional_certificates_return_empty_list_for_coordinator_without_course(client, app):
    seeded = _seed_dashboard_analytics_data(app)

    _login_user(client, seeded['coord_no_course_username'])

    page_res = client.get('/certificados_institucionais')
    list_res = client.get('/api/institutional_certificates')

    assert page_res.status_code == 200
    assert list_res.status_code == 200
    payload = list_res.get_json()
    assert payload['total'] == 0
    assert payload['items'] == []


def test_certificate_send_batch_starts_background_job(client, app, admin_user, monkeypatch):
    event_id = _create_event_for_certs(app)

    with app.app_context():
        event = db.session.get(Event, event_id)
        participant = User(
            username='cert_batch_participant',
            role='participante',
            nome='Participante Cert Batch',
            cpf='77788899900',
            email='batch@test.local',
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.flush()

        activity = event.activities[0]
        db.session.add(Enrollment(
            activity_id=activity.id,
            user_cpf=participant.cpf,
            nome=participant.nome,
            presente=True,
        ))
        db.session.commit()

    monkeypatch.setattr(
        certificates_api.CertificateService,
        'queue_event_certificates',
        lambda self, event_id: (
            True,
            'Envio concluido',
            {'total_enviado': 1, 'sem_email': 0, 'falha_fila': 0}
        )
    )

    class ImmediateThread:
        def __init__(self, target=None, args=None, daemon=None):
            self.target = target
            self.args = args or ()

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(certificates_api, 'Thread', ImmediateThread)

    _login_admin(client)
    res = client.post(f'/api/certificates/send_batch/{event_id}')

    assert res.status_code == 202
    payload = res.get_json()
    assert payload['resultado'] == 'processando'
    assert payload['job_id']

    status_res = client.get(f"/api/certificates/send_batch/status/{payload['job_id']}")
    assert status_res.status_code == 200
    status_payload = status_res.get_json()
    assert status_payload['completed'] is True
    assert status_payload['resultado'] == 'sucesso'
    assert status_payload['total_enviado'] == 1


def test_certificate_management_endpoints_allow_admin_owner_course_coordinator_extensao_and_gestor_view(client, app, admin_user):
    seeded = _seed_certificate_management_data(app)

    for username in ['admin_test', seeded['owner_username'], seeded['coordinator_username'], seeded['extension_username'], seeded['manager_username']]:
        client.get('/api/logout')
        _login_user(client, username)
        res = client.get(f"/api/certificates/list_delivery/{seeded['event_id']}")
        assert res.status_code == 200


def test_event_management_allows_extensao_participants_but_blocks_notifications(client, app, admin_user):
    seeded = _seed_certificate_management_data(app)

    _login_user(client, seeded['extension_username'])

    designer_res = client.get(f"/designer_certificado/{seeded['event_id']}")
    delivery_res = client.get(f"/gerenciar_entregas/{seeded['event_id']}")
    list_res = client.get(f"/api/certificates/list_delivery/{seeded['event_id']}")
    participants_res = client.get(f"/api/participantes_evento/{seeded['event_id']}")
    toggle_res = client.post(f"/api/alternar_presenca/{seeded['enrollment_id']}", json={'presente': False})
    remove_res = client.delete(f"/api/remover_inscricao/{seeded['enrollment_id']}")
    notify_res = client.post(f"/api/notificar_participantes/{seeded['event_id']}", json={
        'assunto': 'Teste',
        'mensagem': 'Mensagem',
    })

    assert designer_res.status_code == 200
    assert delivery_res.status_code == 200
    assert list_res.status_code == 200
    assert participants_res.status_code == 200
    assert toggle_res.status_code == 200
    assert remove_res.status_code == 200
    assert notify_res.status_code == 403

    with app.app_context():
        enrollment = db.session.get(Enrollment, seeded['enrollment_id'])
        assert enrollment is None


def test_event_management_allows_gestor_certificate_visualization_but_blocks_certificate_mutations(client, app, admin_user):
    seeded = _seed_certificate_management_data(app)

    _login_user(client, seeded['manager_username'])

    panel_res = client.get('/eventos_admin')
    page_res = client.get('/api/eventos_admin')
    designer_res = client.get(f"/designer_certificado/{seeded['event_id']}")
    delivery_res = client.get(f"/gerenciar_entregas/{seeded['event_id']}")
    list_res = client.get(f"/api/certificates/list_delivery/{seeded['event_id']}")
    preview_res = client.get(f"/api/certificates/preview/{seeded['enrollment_id']}")
    download_res = client.get(f"/api/certificates/download/{seeded['enrollment_id']}")
    update_email_res = client.post(f"/api/certificates/update_email/{seeded['enrollment_id']}", json={'email': 'gestor@test.local'})
    resend_res = client.post(f"/api/certificates/resend_single/{seeded['enrollment_id']}")
    send_batch_res = client.post(f"/api/certificates/send_batch/{seeded['event_id']}")

    assert panel_res.status_code == 200
    assert page_res.status_code == 200
    payload = page_res.get_json()
    assert any(
        item['id'] == seeded['event_id']
        and item['can_view_certificates'] is True
        and item['can_manage_certificates'] is False
        for item in payload['items']
    )
    assert designer_res.status_code == 200
    assert delivery_res.status_code == 200
    assert list_res.status_code == 200
    assert preview_res.status_code == 200
    assert download_res.status_code == 200
    assert update_email_res.status_code == 403
    assert resend_res.status_code == 403
    assert send_batch_res.status_code == 403


def test_certificate_send_batch_denies_participant(client, app, admin_user):
    seeded = _seed_certificate_management_data(app)

    _login_user(client, seeded['participant_username'])
    res = client.post(f"/api/certificates/send_batch/{seeded['event_id']}")

    assert res.status_code == 403


def test_certificate_download_and_preview_allow_only_owner_participant(client, app, admin_user, monkeypatch, tmp_path):
    seeded = _seed_certificate_management_data(app)
    pdf_path = tmp_path / 'certificate.pdf'
    pdf_path.write_bytes(b'%PDF-1.4\n% mocked certificate\n')

    monkeypatch.setattr(
        certificates_api.cert_service,
        'generate_pdf',
        lambda *args, **kwargs: str(pdf_path)
    )

    _login_user(client, seeded['participant_username'])

    download_res = client.get(f"/api/certificates/download/{seeded['enrollment_id']}")
    preview_res = client.get(f"/api/certificates/preview/{seeded['enrollment_id']}")

    assert download_res.status_code == 200
    assert preview_res.status_code == 200
    assert preview_res.mimetype == 'application/pdf'

    client.get('/api/logout')
    _login_user(client, seeded['outsider_username'])

    denied_download = client.get(f"/api/certificates/download/{seeded['enrollment_id']}")
    denied_preview = client.get(f"/api/certificates/preview/{seeded['enrollment_id']}")

    assert denied_download.status_code == 403
    assert denied_preview.status_code == 403


def test_upload_asset_requires_file(client, app, admin_user):
    _login_admin(client)
    event_id = _create_event_for_certs(app)

    res = client.post(f'/api/certificates/upload_asset/{event_id}', data={})
    assert res.status_code == 400
    assert 'Arquivo não enviado' in res.json['erro']


def test_profile_stats_include_institutional_counts_and_hours(client, app, admin_user):
    _seed_profile_history_data(app)
    _login_participant(client)

    res = client.get('/api/me/history?type=stats')
    assert res.status_code == 200

    payload = res.get_json()
    assert payload['total_hours'] == 6
    assert payload['total_events'] == 1
    assert payload['total_institutional_certificates'] == 1


def test_profile_timeline_merges_event_and_institutional_entries(client, app, admin_user):
    _seed_profile_history_data(app)
    _login_participant(client)

    res = client.get('/api/me/history?type=activities&page=1')
    assert res.status_code == 200

    payload = res.get_json()
    entry_types = {item.get('entry_type') for item in payload['items']}
    assert 'evento' in entry_types
    assert 'institucional' in entry_types


def test_profile_certificates_return_public_download_and_preview_urls(client, app, admin_user):
    _seed_profile_history_data(app)
    _login_participant(client)

    res = client.get('/api/me/history?type=certificates&page=1')
    assert res.status_code == 200

    payload = res.get_json()
    assert payload['items']

    event_item = next(item for item in payload['items'] if item.get('certificate_type') == 'evento')
    inst_item = next(item for item in payload['items'] if item.get('certificate_type') == 'institucional')

    assert event_item['download_url'].startswith('/api/certificates/download_public/')
    assert event_item['preview_url'].startswith('/api/certificates/preview_public/')
    assert inst_item['download_url'].startswith('/api/institutional_certificates/download_public/')
    assert inst_item['preview_url'].startswith('/api/institutional_certificates/preview_public/')


def test_importar_alunos_xlsx_requires_admin(client, app, admin_user):
    with app.app_context():
        participant = User(
            username='participant_import',
            role='participante',
            nome='Participante',
            cpf='321.654.987-00',
            email='participant_import@test.local',
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.commit()

    client.post('/api/login', json={'username': 'participant_import', 'password': '1234'})

    xlsx = _build_students_xlsx_for_api([
        ['Aluno', 'Uni', 'Curso X', 'T1', '12345678900', '', '', '', '', '', '', '', '', '', '', '', '', '', 1, 'a@a.com']
    ])
    res = client.post(
        '/api/importar_alunos_xlsx',
        data={'file': (xlsx, 'alunos.xlsx')},
        content_type='multipart/form-data'
    )
    assert res.status_code == 403


def test_importar_alunos_xlsx_admin_processes_file(client, app, admin_user):
    with app.app_context():
        from app.models import Course

        db.session.add(Course(nome='Direito'))
        db.session.commit()

    _login_admin(client)
    xlsx = _build_students_xlsx_for_api([
        ['Aluno API', 'Uni', 'Direito', 'T1', '12345678900', '', '', '', '', '', 'RA-API', '', '', '', '', '', '', '', 1, 'api@example.com']
    ])

    res = client.post(
        '/api/importar_alunos_xlsx',
        data={'file': (xlsx, 'alunos.xlsx')},
        content_type='multipart/form-data'
    )

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['created'] == 1
    assert payload['updated'] == 0


def test_update_profile_api_updates_name_email(client, app, admin_user):
    _login_admin(client)

    res = client.put('/api/me/profile', json={
        'nome': 'Admin Atualizado',
        'email': 'admin_updated@test.local'
    })

    assert res.status_code == 200
    with app.app_context():
        user = db.session.get(User, 'admin_test')
        assert user.nome == 'Admin Atualizado'
        assert user.email == 'admin_updated@test.local'


def test_change_password_api_requires_current_password(client, admin_user):
    _login_admin(client)
    res = client.put('/api/me/password', json={
        'current_password': 'senha_errada',
        'new_password': 'novasenha123'
    })
    assert res.status_code == 400


def test_password_forgot_always_returns_success(client):
    res = client.post('/api/password/forgot', json={'email': 'naoexiste@test.local'})
    assert res.status_code == 200
    assert 'mensagem' in res.get_json()


def test_password_reset_with_token_updates_password(client, app, admin_user):
    with app.app_context():
        service = AuthService()
        token = service._password_reset_serializer().dumps({'username': 'admin_test'})

    res = client.post('/api/password/reset', json={'token': token, 'password': 'nova12345'})
    assert res.status_code == 200

    login_res = client.post('/api/login', json={'cpf': '00000000000', 'password': 'nova12345'})
    assert login_res.status_code == 200
