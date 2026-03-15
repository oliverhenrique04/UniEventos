import json
from io import BytesIO
from datetime import date, time
from app.models import (
    Event,
    Activity,
    Enrollment,
    User,
    InstitutionalCertificateCategory,
    InstitutionalCertificate,
    InstitutionalCertificateRecipient,
)
from app.extensions import db
from openpyxl import Workbook
from app.services.auth_service import AuthService
from app.api import admin as admin_api
from app.api import certificates as certificates_api


def _login_admin(client):
    client.post('/api/login', json={'username': 'admin_test', 'password': '1234'})


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


def _seed_manual_enrollment_data(app, participant_email='manual_api@test.local'):
    with app.app_context():
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
        }


def _login_participant(client):
    client.post('/api/login', json={'username': 'participant_test', 'password': '1234'})


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

def test_login_api(client, admin_user):
    res = client.post('/api/login', json={'username': 'admin_test', 'password': '1234'})
    assert res.status_code == 200
    assert res.json['status'] == 'success'

def test_login_fail(client):
    res = client.post('/api/login', json={'username': 'wrong', 'password': '123'})
    assert res.status_code == 401

def test_create_event_api(client, admin_user):
    # Login first
    client.post('/api/login', json={'username': 'admin_test', 'password': '1234'})
    
    data = {
        'nome': 'API Event',
        'descricao': 'Via API',
        'is_rapido': True,
        'data_inicio': '2030-01-01',
        'hora_inicio': '10:00'
    }
    res = client.post('/api/criar_evento', json=data)
    assert res.status_code == 200
    assert 'link' in res.json


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
        assert {'date_fixed', 'hash', 'qrcode'}.issubset(fixed_ids)


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
