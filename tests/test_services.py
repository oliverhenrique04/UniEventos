import pytest
import json
import os
from io import BytesIO
from datetime import date, time
from app.services.auth_service import AuthService
from app.services.event_service import EventService
from app.services.certificate_service import CertificateService
from app.services.admin_service import AdminService
from app.services.email_template_service import EmailTemplateService
from app.models import User
from app.extensions import db
from app.models import Event, Course, Activity, Enrollment
from openpyxl import Workbook

def test_auth_service_register(app):
    service = AuthService()
    data = {'username': 'newuser', 'password': '123', 'nome': 'New', 'cpf': '99999999999'}
    user = service.register_user(data)
    assert user.username == '99999999999'
    assert user.check_password('123')

def test_auth_service_duplicate(app, admin_user):
    service = AuthService()
    data = {'username': 'admin_test', 'password': '123', 'nome': 'New', 'cpf': '00000000000'}
    with pytest.raises(ValueError):
        service.register_user(data)

def test_event_service_create(app, admin_user):
    service = EventService()
    data = {
        'nome': 'Test Event',
        'descricao': 'Desc',
        'is_rapido': True,
        'data_inicio': '2026-01-01',
        'hora_inicio': '10:00',
        'data_fim': '2026-01-01',
        'hora_fim': '12:00'
    }
    event = service.create_event(admin_user.username, data)
    assert event.nome == 'Test Event'
    assert event.tipo == 'RAPIDO'
    assert len(event.activities) == 1
    assert event.activities[0].nome == 'Check-in Presença'


def test_event_service_create_fast_event_defaults_start_date_to_today(app, admin_user):
    service = EventService()
    data = {
        'nome': 'Fast Event Sem Data',
        'descricao': 'Desc',
        'is_rapido': True,
        'hora_inicio': '10:00',
        'data_inicio': '',
        'data_fim': '',
    }

    event = service.create_event(admin_user.username, data)

    assert event.tipo == 'RAPIDO'
    assert event.data_inicio == date.today()
    assert event.data_fim == date.today()


def test_event_service_update_event_sends_email_to_owner(app):
    with app.app_context():
        owner = User(
            username='event_owner_update',
            role='professor',
            nome='Owner Update',
            cpf='44455566677',
            email='owner_update@test.local',
        )
        owner.set_password('1234')
        db.session.add(owner)
        db.session.commit()

        service = EventService()
        sent_payloads = []
        service.notification_service.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

        event = service.create_event(owner.username, {
            'nome': 'Evento Original',
            'descricao': 'Desc',
            'is_rapido': True,
            'data_inicio': '2030-01-01',
            'hora_inicio': '10:00',
        })
        sent_payloads.clear()

        updated, msg = service.update_event(event.id, owner.username, owner.role, {
            'nome': 'Evento Atualizado',
            'descricao': 'Desc atualizada',
            'is_rapido': True,
            'data_inicio': '2030-01-02',
            'hora_inicio': '11:00',
        })

        assert updated is not None
        assert msg == 'Evento atualizado com sucesso!'
        assert len(sent_payloads) == 1
        assert sent_payloads[0]['template_name'] == 'event_updated_owner.html'
        assert sent_payloads[0]['to_email'] == 'owner_update@test.local'


def test_event_service_delete_event_sends_email_to_owner(app):
    with app.app_context():
        owner = User(
            username='event_owner_delete',
            role='professor',
            nome='Owner Delete',
            cpf='55566677788',
            email='owner_delete@test.local',
        )
        owner.set_password('1234')
        db.session.add(owner)
        db.session.commit()

        service = EventService()
        sent_payloads = []
        service.notification_service.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

        event = service.create_event(owner.username, {
            'nome': 'Evento Para Excluir',
            'descricao': 'Desc',
            'is_rapido': True,
            'data_inicio': '2030-01-03',
            'hora_inicio': '12:00',
        })
        sent_payloads.clear()

        success, msg = service.delete_event(event.id, owner.username, owner.role)

        assert success is True
        assert msg == 'Evento removido com sucesso.'
        assert len(sent_payloads) == 1
        assert sent_payloads[0]['template_name'] == 'event_deleted_owner.html'
        assert sent_payloads[0]['to_email'] == 'owner_delete@test.local'


def test_admin_service_manual_enroll_sends_email_to_added_user(app, admin_user):
    with app.app_context():
        participant = User(
            username='manual_email_user',
            role='participante',
            nome='Participante Manual',
            cpf='11122233344',
            email='manual_email@test.local',
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.flush()

        event = Event(
            owner_username='admin_test',
            nome='Evento Manual',
            descricao='Descricao do evento',
            tipo='PADRAO',
            token_publico='token-manual-email',
            data_inicio=date(2030, 2, 10),
            hora_inicio=time(18, 0),
        )
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            nome='Oficina Pratica',
            local='Laboratorio 3',
            descricao='Descricao da atividade',
            data_atv=date(2030, 2, 11),
            hora_atv=time(19, 30),
            carga_horaria=4,
            vagas=25,
        )
        db.session.add(activity)
        db.session.commit()

        service = AdminService()
        sent_payloads = []
        service.notification_service.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

        success, msg = service.manual_enroll(participant.cpf, activity.id)

        assert success is True
        assert msg == 'Inscrição realizada com sucesso.'
        enrollment = Enrollment.query.filter_by(user_cpf=participant.cpf, activity_id=activity.id).first()
        assert enrollment is not None
        assert enrollment.presente is True
        assert len(sent_payloads) == 1
        assert sent_payloads[0]['to_email'] == 'manual_email@test.local'
        assert sent_payloads[0]['subject'] == 'Você foi adicionado ao evento: Evento Manual'
        assert sent_payloads[0]['template_name'] == 'manual_enrollment_confirmation.html'
        assert sent_payloads[0]['template_data']['user_name'] == 'Participante Manual'
        assert sent_payloads[0]['template_data']['event_name'] == 'Evento Manual'
        assert sent_payloads[0]['template_data']['activity_name'] == 'Oficina Pratica'
        assert sent_payloads[0]['template_data']['event_date'] == '11/02/2030'
        assert sent_payloads[0]['template_data']['event_time'] == '19:30'
        assert sent_payloads[0]['template_data']['event_location'] == 'Laboratorio 3'
        assert sent_payloads[0]['template_data']['event_description'] == 'Descricao da atividade'
        assert sent_payloads[0]['template_data']['event_details_url'].endswith('/inscrever/token-manual-email')
        assert sent_payloads[0]['template_data']['my_events_url'].endswith('/meus_eventos')


def test_admin_service_manual_enroll_without_email_does_not_send_notification(app, admin_user):
    with app.app_context():
        participant = User(
            username='manual_no_email_user',
            role='participante',
            nome='Participante Sem Email',
            cpf='11122233355',
            email=None,
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.flush()

        event = Event(
            owner_username='admin_test',
            nome='Evento Sem Email',
            descricao='Descricao',
            tipo='PADRAO',
            token_publico='token-sem-email',
            data_inicio=date(2030, 3, 10),
            hora_inicio=time(9, 0),
        )
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            nome='Painel',
            local='Auditorio',
            descricao='Atividade sem email',
            data_atv=date(2030, 3, 10),
            hora_atv=time(10, 0),
            carga_horaria=2,
            vagas=40,
        )
        db.session.add(activity)
        db.session.commit()

        service = AdminService()
        sent_payloads = []
        service.notification_service.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

        success, msg = service.manual_enroll(participant.cpf, activity.id)

        assert success is True
        assert msg == 'Inscrição realizada com sucesso.'
        assert Enrollment.query.filter_by(user_cpf=participant.cpf, activity_id=activity.id).first() is not None
        assert sent_payloads == []


def test_admin_service_manual_enroll_duplicate_does_not_send_notification(app, admin_user):
    with app.app_context():
        participant = User(
            username='manual_duplicate_user',
            role='participante',
            nome='Participante Duplicado',
            cpf='11122233366',
            email='manual_duplicate@test.local',
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.flush()

        event = Event(
            owner_username='admin_test',
            nome='Evento Duplicado',
            descricao='Descricao',
            tipo='PADRAO',
            token_publico='token-duplicado',
            data_inicio=date(2030, 4, 1),
            hora_inicio=time(14, 0),
        )
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            nome='Mesa Redonda',
            local='Sala 2',
            descricao='Descricao',
            data_atv=date(2030, 4, 1),
            hora_atv=time(15, 0),
            carga_horaria=2,
            vagas=20,
        )
        db.session.add(activity)
        db.session.flush()

        db.session.add(Enrollment(
            activity_id=activity.id,
            user_cpf=participant.cpf,
            nome=participant.nome,
            presente=True,
        ))
        db.session.commit()

        service = AdminService()
        sent_payloads = []
        service.notification_service.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

        success, msg = service.manual_enroll(participant.cpf, activity.id)

        assert success is False
        assert msg == 'Usuário já está inscrito nesta atividade.'
        assert sent_payloads == []


def test_manual_enrollment_email_template_renders_with_base_layout():
    service = EmailTemplateService()

    html = service.render_template('manual_enrollment_confirmation.html', {
        'user_name': 'Participante Teste',
        'event_name': 'Evento Template',
        'activity_name': 'Atividade Template',
        'event_date': '10/02/2030',
        'event_time': '19:30',
        'event_location': 'Laboratorio 1',
        'event_description': 'Descricao do template',
        'event_details_url': 'http://localhost:5000/inscrever/token-template',
        'my_events_url': 'http://localhost:5000/meus_eventos',
        'year': 2026,
        'subject': 'Você foi adicionado ao evento: Evento Template',
    })

    assert 'EuroEventos' in html
    assert 'Você foi adicionado a um evento' in html
    assert 'Evento Template' in html
    assert 'Atividade Template' in html
    assert 'Abrir página do evento' in html


def test_event_service_get_event_participants_paginated_returns_newest_first(app, admin_user):
    with app.app_context():
        event = Event(
            owner_username=admin_user.username,
            nome='Evento Ordenacao',
            descricao='Descricao',
            tipo='PADRAO',
            token_publico='token-ordenacao',
            data_inicio=date(2030, 5, 10),
            hora_inicio=time(9, 0),
        )
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            nome='Atividade Ordenacao',
            local='Sala 10',
            descricao='Descricao',
            data_atv=date(2030, 5, 10),
            hora_atv=time(10, 0),
            carga_horaria=2,
            vagas=30,
        )
        db.session.add(activity)
        db.session.flush()

        participant_1 = User(
            username='participant_order_1',
            role='participante',
            nome='Primeiro Participante',
            cpf='99988877711',
            email='participant1@test.local',
        )
        participant_1.set_password('1234')

        participant_2 = User(
            username='participant_order_2',
            role='participante',
            nome='Segundo Participante',
            cpf='99988877722',
            email='participant2@test.local',
        )
        participant_2.set_password('1234')

        db.session.add_all([participant_1, participant_2])
        db.session.flush()

        enrollment_1 = Enrollment(
            activity_id=activity.id,
            user_cpf=participant_1.cpf,
            nome=participant_1.nome,
            presente=False,
        )
        db.session.add(enrollment_1)
        db.session.flush()

        enrollment_2 = Enrollment(
            activity_id=activity.id,
            user_cpf=participant_2.cpf,
            nome=participant_2.nome,
            presente=True,
        )
        db.session.add(enrollment_2)
        db.session.commit()

        pagination = EventService().get_event_participants_paginated(event.id, page=1, per_page=10)

        assert [item.id for item in pagination.items] == [enrollment_2.id, enrollment_1.id]


def test_certificate_service_generates_pdf_with_bounded_overflow_text(app, admin_user):
    with app.app_context():
        output_dir = os.path.join(app.root_path, 'static', 'certificates', 'generated')
        os.makedirs(output_dir, exist_ok=True)

        event = Event(
            owner_username='admin_test',
            nome='Evento Overflow',
            descricao='Teste bloco de texto',
            tipo='RAPIDO',
            data_inicio=date(2030, 5, 1),
            hora_inicio=time(9, 0),
            cert_template_json=json.dumps({
                'version': 2,
                'document': {'gridSize': 2, 'snap': True, 'guides': True},
                'elements': [
                    {
                        'id': 'txt_block',
                        'type': 'text',
                        'text': 'CERTIFICAMOS QUE {{NOME}} PARTICIPOU DO EVENTO {{EVENTO}} COM CARGA DE {{HORAS}} HORAS. ESTE TEXTO É LONGO PARA TESTAR AJUSTE NO BLOCO.',
                        'x': 50,
                        'y': 50,
                        'w': 22,
                        'h': 5,
                        'font': 36,
                        'color': '#111111',
                        'align': 'justify',
                        'bold': False,
                        'italic': False,
                        'font_family': 'Helvetica',
                        'zIndex': 1,
                        'visible': True
                    }
                ]
            })
        )

        user = User(
            username='cert_user_overflow',
            role='student',
            nome='Aluno Overflow',
            cpf='10000000001',
            email='overflow@example.com'
        )
        user.set_password('1234')

        db.session.add(event)
        db.session.add(user)
        db.session.commit()

        service = CertificateService()
        pdf_path = service.generate_pdf(event, user, activities=[], total_hours=10)

        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0


def test_certificate_service_generates_pdf_with_partial_rich_text_styles(app, admin_user):
    with app.app_context():
        output_dir = os.path.join(app.root_path, 'static', 'certificates', 'generated')
        os.makedirs(output_dir, exist_ok=True)

        event = Event(
            owner_username='admin_test',
            nome='Evento Rich Text',
            descricao='Teste estilo parcial',
            tipo='RAPIDO',
            data_inicio=date(2030, 6, 2),
            hora_inicio=time(11, 0),
            cert_template_json=json.dumps({
                'version': 2,
                'document': {'gridSize': 2, 'snap': True, 'guides': True},
                'elements': [
                    {
                        'id': 'txt_rich',
                        'type': 'text',
                        'text': 'Participante: {{NOME}}',
                        'x': 50,
                        'y': 40,
                        'w': 45,
                        'h': 8,
                        'font': 26,
                        'color': '#222222',
                        'align': 'center',
                        'bold': False,
                        'italic': False,
                        'font_family': 'Helvetica',
                        'text_styles': {
                            '0': {
                                '13': {'fontWeight': 'bold', 'fill': '#0f172a', 'fontSize': 30},
                                '14': {'fontStyle': 'italic', 'fill': '#1d4ed8', 'fontFamily': 'Times-Roman'}
                            }
                        },
                        'zIndex': 1,
                        'visible': True
                    }
                ]
            })
        )

        user = User(
            username='cert_user_rich',
            role='student',
            nome='Aluno Estilizado',
            cpf='10000000002',
            email='rich@example.com'
        )
        user.set_password('1234')

        db.session.add(event)
        db.session.add(user)
        db.session.commit()

        service = CertificateService()
        pdf_path = service.generate_pdf(event, user, activities=[], total_hours=8)

        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0


def test_certificate_service_generates_pdf_with_unsupported_font_family_fallback(app, admin_user):
    with app.app_context():
        output_dir = os.path.join(app.root_path, 'static', 'certificates', 'generated')
        os.makedirs(output_dir, exist_ok=True)

        event = Event(
            owner_username='admin_test',
            nome='Evento Fonte Fallback',
            descricao='Teste fonte fallback',
            tipo='RAPIDO',
            data_inicio=date(2030, 7, 1),
            hora_inicio=time(9, 0),
            cert_template_json=json.dumps({
                'version': 2,
                'document': {'gridSize': 2, 'snap': True, 'guides': True},
                'elements': [
                    {
                        'id': 'txt_custom',
                        'type': 'text',
                        'text': 'Texto com fonte nao suportada',
                        'x': 50,
                        'y': 50,
                        'w': 60,
                        'h': 12,
                        'font': 24,
                        'color': '#111111',
                        'align': 'center',
                        'font_family': 'Arial',
                        'zIndex': 1,
                        'visible': True
                    }
                ]
            })
        )

        user = User(
            username='cert_user_font_fallback',
            role='student',
            nome='Aluno Fonte Fallback',
            cpf='10000000003',
            email='font-fallback@example.com'
        )
        user.set_password('1234')

        db.session.add(event)
        db.session.add(user)
        db.session.commit()

        service = CertificateService()
        pdf_path = service.generate_pdf(event, user, activities=[], total_hours=4)

        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0


def test_certificate_service_normalize_template_payload_restores_fixed_validation_elements():
    normalized = CertificateService.normalize_template_payload({
        'version': 2,
        'document': {'gridSize': 2, 'snap': True, 'guides': True},
        'elements': [
            {
                'id': 'date_fixed',
                'type': 'text',
                'text': 'Data estática',
                'x': 50,
                'y': 96,
                'w': 50,
                'h': 4,
                'font': 12,
                'visible': False,
            },
            {
                'id': 'hash',
                'type': 'text',
                'text': 'HASH-FIXO',
                'x': 90,
                'y': 95,
                'w': 12,
                'h': 4,
                'font': 12,
                'font_family': 'Arial',
                'visible': False,
            },
            {
                'id': 'qrcode',
                'type': 'image',
                'x': 90,
                'y': 88,
                'w': 12,
                'h': 12,
                'visible': False,
            },
        ],
    })

    by_id = {item['id']: item for item in normalized['elements']}

    assert by_id['date_fixed']['visible'] is True
    assert '{{DATA}}' in by_id['date_fixed']['text']
    assert by_id['hash']['visible'] is True
    assert by_id['hash']['text'] == '{{HASH}}'
    assert by_id['hash']['font_family'] == 'Courier'
    assert by_id['qrcode']['visible'] is True
    assert by_id['qrcode']['type'] == 'qr'


def _build_students_xlsx(rows, include_email=True):
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


def test_admin_service_import_students_xlsx_upserts_and_creates_with_email(app, admin_user):
    with app.app_context():
        c1 = Course(nome='Engenharia de Software')
        c2 = Course(nome='Direito')
        db.session.add_all([c1, c2])

        existing = User(
            username='user_old',
            role='professor',
            nome='Nome Antigo',
            cpf='123.456.789-00',
            ra='RA-OLD',
            email='old@example.com',
            course_id=c1.id,
            can_create_events=True,
        )
        existing.set_password('1234')
        db.session.add(existing)
        db.session.commit()

        rows = [
            [
                'Nome Atualizado', 'Uni', 'Direito', 'T1', '12345678900', '2000-01-01',
                'M', 'S', 'Mae', 'Superior', 'RA-NEW', 'Noite', '2026.1', 'Rua 1',
                'Centro', '70000000', 'Brasilia', 'DF', 1, 'updated@example.com'
            ],
            [
                'Aluno Novo', 'Uni', 'Engenharia de Software', 'T2', '98765432100', '2001-02-03',
                'F', 'S', 'Mae 2', 'Superior', 'RA-002', 'Manha', '2026.1', 'Rua 2',
                'Bairro', '70000001', 'Brasilia', 'DF', 1, 'novo@example.com'
            ],
            [
                'Aluno Sem Email', 'Uni', 'Engenharia de Software', 'T3', '11122233344', '2001-02-03',
                'F', 'S', 'Mae 3', 'Superior', 'RA-003', 'Manha', '2026.1', 'Rua 3',
                'Bairro', '70000002', 'Brasilia', 'DF', 1, ''
            ],
        ]
        xlsx_stream = _build_students_xlsx(rows, include_email=True)

        service = AdminService()
        result = service.import_students_xlsx(xlsx_stream)

        assert result['created'] == 1
        assert result['updated'] == 1
        assert result['total_rows'] == 3
        assert any('Novo aluno sem EMAIL' in err for err in result['errors'])

        updated = User.query.filter_by(cpf='123.456.789-00').first()
        assert updated is not None
        assert updated.nome == 'Nome Atualizado'
        assert updated.ra == 'RA-NEW'
        assert updated.curso == 'Direito'
        assert updated.role == 'professor'
        assert updated.can_create_events is True

        created = User.query.filter_by(cpf='987.654.321-00').first()
        assert created is not None
        assert created.username == '98765432100'
        assert created.role == 'participante'
        assert created.can_create_events is False


def test_admin_service_import_students_xlsx_requires_required_headers(app, admin_user):
    with app.app_context():
        wb = Workbook()
        ws = wb.active
        ws.append(['ALUNO_NOME', 'CURSO'])
        ws.append(['Aluno', 'Curso'])

        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)

        result = AdminService().import_students_xlsx(stream)

        assert result['created'] == 0
        assert result['updated'] == 0
        assert any('Colunas obrigatórias ausentes' in err for err in result['errors'])


def test_auth_service_update_profile_no_real_changes_does_not_send_email(app):
    with app.app_context():
        user = User(
            username='profile_user_same',
            role='participante',
            nome='Nome Original',
            cpf='22233344455',
            email='User@Test.local',
        )
        user.set_password('1234')
        db.session.add(user)
        db.session.commit()

        sent_payloads = []
        service = AuthService()
        service.notifier.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

        success, msg = service.update_profile(user, '  Nome Original  ', ' user@test.local ')

        assert success is True
        assert msg == 'Nenhuma alteração detectada.'
        assert sent_payloads == []


def test_auth_service_update_profile_sends_only_changed_fields(app):
    with app.app_context():
        user = User(
            username='profile_user_changed',
            role='participante',
            nome='Nome Antigo',
            cpf='33344455566',
            email='old_email@test.local',
        )
        user.set_password('1234')
        db.session.add(user)
        db.session.commit()

        sent_payloads = []
        service = AuthService()
        service.notifier.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

        success, msg = service.update_profile(user, 'Nome Novo', 'old_email@test.local')

        assert success is True
        assert msg == 'Perfil atualizado com sucesso.'
        assert len(sent_payloads) == 1
        template_data = sent_payloads[0]['template_data']
        assert template_data['changed_fields'] == [
            {
                'label': 'Nome',
                'old': 'Nome Antigo',
                'new': 'Nome Novo',
            }
        ]
