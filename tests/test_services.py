import pytest
import json
import os
from io import BytesIO
from datetime import date, time
from types import SimpleNamespace
from app.services.auth_service import AuthService
from app.services.event_service import EventService
from app.services.certificate_service import CertificateService
from app.services.institutional_certificate_service import InstitutionalCertificateService
from app.services.admin_service import AdminService
from app.services.email_template_service import EmailTemplateService
from app.models import User
from app.extensions import db
from app.models import Event, Course, Activity, Enrollment, EventRegistration
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
        'carga_horaria_rapida': 2,
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
        'carga_horaria_rapida': 2,
        'hora_inicio': '10:00',
        'data_inicio': '',
        'data_fim': '',
    }

    event = service.create_event(admin_user.username, data)

    assert event.tipo == 'RAPIDO'
    assert event.data_inicio == date.today()
    assert event.data_fim == date.today()


def test_event_service_create_persists_allowed_roles_and_registration_categories(app, admin_user):
    service = EventService()
    event = service.create_event(admin_user.username, {
        'nome': 'Evento com Perfis e Categorias',
        'descricao': 'Desc',
        'is_rapido': True,
        'carga_horaria_rapida': 2,
        'data_inicio': '2030-05-01',
        'hora_inicio': '10:00',
        'data_fim': '2030-05-01',
        'hora_fim': '12:00',
        'perfis_habilitados': ['participante', 'professor'],
        'categorias_inscricao': [
            {'nome': 'Aluno', 'vagas': 3},
            {'nome': 'Comunidade Externa', 'vagas': -1},
        ],
    })

    assert event.allowed_roles_list == ['participante', 'professor']
    assert [(item.nome, item.vagas) for item in event.registration_categories] == [
        ('Aluno', 3),
        ('Comunidade Externa', -1),
    ]


def test_event_service_reuses_event_registration_category_and_cleans_up_after_last_unenroll(app, admin_user):
    participant = User(
        username='participant_category_flow',
        role='participante',
        nome='Participante Categoria',
        cpf='12345000001',
    )
    participant.set_password('1234')
    db.session.add(participant)
    db.session.commit()

    service = EventService()
    event = service.create_event(admin_user.username, {
        'nome': 'Evento com Duas Atividades',
        'descricao': 'Desc',
        'is_rapido': False,
        'data_inicio': '2030-06-10',
        'hora_inicio': '18:00',
        'data_fim': '2030-06-10',
        'hora_fim': '22:00',
        'perfis_habilitados': ['participante'],
        'categorias_inscricao': [
            {'nome': 'Aluno', 'vagas': 2},
            {'nome': 'Ouvinte', 'vagas': 5},
        ],
        'atividades': [
            {
                'nome': 'Atividade 1',
                'local': 'Sala 1',
                'descricao': 'Primeira',
                'data_atv': '2030-06-10',
                'hora_atv': '18:30',
                'horas': 2,
                'vagas': 10,
            },
            {
                'nome': 'Atividade 2',
                'local': 'Sala 2',
                'descricao': 'Segunda',
                'data_atv': '2030-06-10',
                'hora_atv': '20:30',
                'horas': 2,
                'vagas': 10,
            },
        ],
    })

    categories = {category.nome: category for category in event.registration_categories}
    activities = sorted(event.activities, key=lambda activity: activity.id)

    enrollment1, message1 = service.toggle_enrollment(
        participant,
        activities[0].id,
        'inscrever',
        category_id=categories['Aluno'].id,
        actor_user=participant,
    )
    assert message1 == 'Inscrição Realizada!'
    assert enrollment1 is not None

    enrollment2, message2 = service.toggle_enrollment(
        participant,
        activities[1].id,
        'inscrever',
        category_id=categories['Ouvinte'].id,
        actor_user=participant,
    )
    assert message2 == 'Inscrição Realizada!'
    assert enrollment2 is not None
    assert enrollment1.event_registration_id == enrollment2.event_registration_id

    registration = EventRegistration.query.filter_by(event_id=event.id, user_cpf=participant.cpf).first()
    assert registration is not None
    assert registration.category_id == categories['Aluno'].id

    _, leave_message_1 = service.toggle_enrollment(participant, activities[0].id, 'sair', actor_user=participant)
    assert leave_message_1 == 'Desinscrição realizada.'
    assert EventRegistration.query.filter_by(event_id=event.id, user_cpf=participant.cpf).first() is not None

    _, leave_message_2 = service.toggle_enrollment(participant, activities[1].id, 'sair', actor_user=participant)
    assert leave_message_2 == 'Desinscrição realizada.'
    assert EventRegistration.query.filter_by(event_id=event.id, user_cpf=participant.cpf).first() is None


def test_event_service_blocks_category_quota_before_creating_activity_enrollment(app, admin_user):
    participant_a = User(
        username='quota_user_a',
        role='participante',
        nome='Quota A',
        cpf='12345000002',
    )
    participant_a.set_password('1234')
    participant_b = User(
        username='quota_user_b',
        role='participante',
        nome='Quota B',
        cpf='12345000003',
    )
    participant_b.set_password('1234')
    db.session.add_all([participant_a, participant_b])
    db.session.commit()

    service = EventService()
    event = service.create_event(admin_user.username, {
        'nome': 'Evento com Cota',
        'descricao': 'Desc',
        'is_rapido': False,
        'data_inicio': '2030-07-10',
        'hora_inicio': '18:00',
        'data_fim': '2030-07-10',
        'hora_fim': '20:00',
        'perfis_habilitados': ['participante'],
        'categorias_inscricao': [{'nome': 'Aluno', 'vagas': 1}],
        'atividades': [
            {
                'nome': 'Atividade Unica',
                'local': 'Sala',
                'descricao': 'Atividade',
                'data_atv': '2030-07-10',
                'hora_atv': '18:30',
                'horas': 2,
                'vagas': 20,
            }
        ],
    })

    category = event.registration_categories[0]
    activity = event.activities[0]

    enrollment_a, message_a = service.toggle_enrollment(
        participant_a,
        activity.id,
        'inscrever',
        category_id=category.id,
        actor_user=participant_a,
    )
    assert message_a == 'Inscrição Realizada!'
    assert enrollment_a is not None

    enrollment_b, message_b = service.toggle_enrollment(
        participant_b,
        activity.id,
        'inscrever',
        category_id=category.id,
        actor_user=participant_b,
    )
    assert enrollment_b is None
    assert message_b == 'Categoria de inscrição lotada.'
    assert Enrollment.query.filter_by(activity_id=activity.id, user_cpf=participant_b.cpf).first() is None


def test_event_service_confirm_attendance_creates_event_registration_for_fast_event_checkin(app, admin_user):
    participant = User(
        username='checkin_category_user',
        role='participante',
        nome='Participante Checkin',
        cpf='12345000004',
    )
    participant.set_password('1234')
    db.session.add(participant)
    db.session.commit()

    service = EventService()
    event = service.create_event(admin_user.username, {
        'nome': 'Evento Rapido com Categoria',
        'descricao': 'Desc',
        'is_rapido': True,
        'carga_horaria_rapida': 2,
        'data_inicio': '2030-08-01',
        'hora_inicio': '19:00',
        'data_fim': '2030-08-01',
        'hora_fim': '21:00',
        'perfis_habilitados': ['participante'],
        'categorias_inscricao': [{'nome': 'Aluno', 'vagas': 10}],
    })

    category = event.registration_categories[0]
    activity = event.activities[0]

    success, message, enrollment = service.confirm_attendance(
        participant,
        activity.id,
        event.id,
        lat=-15.80,
        lon=-47.90,
        category_id=category.id,
    )

    assert success is True
    assert message == 'Presença confirmada!'
    assert enrollment is not None
    assert enrollment.presente is True

    registration = EventRegistration.query.filter_by(event_id=event.id, user_cpf=participant.cpf).first()
    assert registration is not None
    assert registration.category_id == category.id
    assert enrollment.event_registration_id == registration.id


def test_event_service_can_manage_event_allows_coordinator_course_scope_but_keeps_delete_owner_only(app):
    with app.app_context():
        course = Course(nome='Curso Permissoes')
        db.session.add(course)
        db.session.flush()

        admin = User(username='admin_owner_scope', role='admin', nome='Admin Scope', cpf='10020030040')
        admin.set_password('1234')

        owner = User(
            username='owner_scope',
            role='professor',
            nome='Owner Scope',
            cpf='10020030041',
            course_id=course.id,
            can_create_events=True,
        )
        owner.set_password('1234')

        gestor = User(
            username='gestor_scope',
            role='gestor',
            nome='Gestor Scope',
            cpf='10020030042',
            course_id=course.id,
        )
        gestor.set_password('1234')

        coordenador = User(
            username='coord_scope',
            role='coordenador',
            nome='Coord Scope',
            cpf='10020030043',
            course_id=course.id,
        )
        coordenador.set_password('1234')

        extensao = User(
            username='ext_scope',
            role='extensao',
            nome='Ext Scope',
            cpf='10020030044',
            course_id=course.id,
        )
        extensao.set_password('1234')

        db.session.add_all([admin, owner, gestor, coordenador, extensao])
        db.session.flush()

        event = Event(
            owner_username=owner.username,
            nome='Evento Escopo',
            descricao='Desc',
            tipo='PADRAO',
            data_inicio=date(2030, 3, 10),
            hora_inicio=time(19, 0),
            data_fim=date(2030, 3, 10),
            hora_fim=time(21, 0),
            course_id=course.id,
        )
        db.session.add(event)
        db.session.commit()

        assert EventService.can_view_event(gestor, event) is True
        assert EventService.can_manage_event(gestor, event) is False
        assert EventService.can_view_event_certificates(gestor, event) is True
        assert EventService.can_manage_event_certificates(gestor, event) is False
        assert EventService.can_view_event(coordenador, event) is True
        assert EventService.can_manage_event(coordenador, event) is True
        assert EventService.can_delete_event(coordenador, event) is False
        assert EventService.can_manage_event(extensao, event) is False
        assert EventService.can_manage_event_participants(extensao, event) is True
        assert EventService.can_add_event_participants(extensao, event) is True
        assert EventService.can_notify_event_participants(extensao, event) is False
        assert EventService.can_manage_event(owner, event) is True
        assert EventService.can_delete_event(owner, event) is True
        assert EventService.can_manage_event(admin, event) is True


def test_event_service_create_standard_event_persists_multiple_speakers(app, admin_user):
    service = EventService()
    event = service.create_event(admin_user.username, {
        'nome': 'Evento com Multiplos Palestrantes',
        'descricao': 'Desc',
        'is_rapido': False,
        'data_inicio': '2030-03-01',
        'hora_inicio': '19:00',
        'data_fim': '2030-03-01',
        'hora_fim': '21:00',
        'atividades': [
            {
                'nome': 'Mesa Redonda',
                'palestrantes': [
                    {'nome': 'Profa. Teste', 'email': 'profa.teste@example.com', 'ordem': 0},
                    {'nome': 'Dr. Convidado', 'email': 'dr.convidado@example.com', 'ordem': 1},
                ],
                'local': 'Sala 5',
                'descricao': 'Atividade com contato do palestrante',
                'data_atv': '2030-03-01',
                'hora_atv': '19:30',
                'horas': 2,
                'vagas': 40,
            }
        ],
    })

    assert event.tipo == 'PADRAO'
    assert len(event.activities) == 1
    assert len(event.activities[0].speakers) == 2
    assert event.activities[0].palestrante == 'Profa. Teste'
    assert event.activities[0].email_palestrante == 'profa.teste@example.com'
    assert event.activities[0].palestrantes_label == 'Profa. Teste, Dr. Convidado'


def test_event_service_create_standard_event_accepts_legacy_speaker_payload(app, admin_user):
    service = EventService()
    event = service.create_event(admin_user.username, {
        'nome': 'Evento Legado com Palestrante',
        'descricao': 'Desc',
        'is_rapido': False,
        'data_inicio': '2030-03-02',
        'hora_inicio': '19:00',
        'data_fim': '2030-03-02',
        'hora_fim': '21:00',
        'atividades': [
            {
                'nome': 'Painel Antigo',
                'palestrante': 'Profa. Legado',
                'email_palestrante': 'profa.legado@example.com',
                'local': 'Sala 6',
                'descricao': 'Atividade em payload legado',
                'data_atv': '2030-03-02',
                'hora_atv': '19:30',
                'horas': 2,
                'vagas': 40,
            }
        ],
    })

    assert len(event.activities) == 1
    assert len(event.activities[0].speakers) == 1
    assert event.activities[0].speakers[0].nome == 'Profa. Legado'
    assert event.activities[0].speakers[0].email == 'profa.legado@example.com'


def test_activity_legacy_speaker_fields_still_expose_canonical_payload(app):
    with app.app_context():
        owner = User(username='legacy_owner', role='professor', nome='Owner Legado', cpf='55566677788')
        owner.set_password('1234')
        db.session.add(owner)
        db.session.flush()

        event = Event(
            owner_username=owner.username,
            nome='Evento Legado',
            descricao='Desc',
            tipo='PADRAO',
            data_inicio=date(2030, 3, 3),
            hora_inicio=time(19, 0),
            data_fim=date(2030, 3, 3),
            hora_fim=time(21, 0),
        )
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            nome='Atividade Legada',
            palestrante='Prof. Legado',
            email_palestrante='prof.legado@example.com',
            local='Sala 1',
            descricao='Atividade migrada',
            data_atv=date(2030, 3, 3),
            hora_atv=time(19, 30),
            carga_horaria=2,
            vagas=20,
        )
        db.session.add(activity)
        db.session.commit()

        assert activity.speakers == []
        assert activity.get_speakers_payload(include_emails=True) == [{
            'id': None,
            'nome': 'Prof. Legado',
            'email': 'prof.legado@example.com',
            'ordem': 0,
        }]
        assert activity.palestrantes_label == 'Prof. Legado'


def test_event_service_update_event_sends_email_to_owner(app):
    with app.app_context():
        owner = User(
            username='event_owner_update',
            role='professor',
            nome='Owner Update',
            cpf='44455566677',
            email='owner_update@test.local',
            can_create_events=True,
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
            'carga_horaria_rapida': 2,
            'data_inicio': '2030-01-01',
            'hora_inicio': '10:00',
        })
        sent_payloads.clear()

        updated, msg = service.update_event(event.id, owner, {
            'nome': 'Evento Atualizado',
            'descricao': 'Desc atualizada',
            'is_rapido': True,
            'carga_horaria_rapida': 2,
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
            can_create_events=True,
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
            'carga_horaria_rapida': 2,
            'data_inicio': '2030-01-03',
            'hora_inicio': '12:00',
        })
        sent_payloads.clear()

        success, msg = service.delete_event(event.id, owner)

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

    assert by_id['name_fixed']['visible'] is True
    assert by_id['name_fixed']['text'] == '{{NOME}}'
    assert by_id['date_fixed']['visible'] is True
    assert '{{DATA}}' in by_id['date_fixed']['text']
    assert by_id['hash']['visible'] is True
    assert by_id['hash']['text'] == '{{HASH}}'
    assert by_id['hash']['font_family'] == 'Courier'
    assert by_id['qrcode']['visible'] is True
    assert by_id['qrcode']['type'] == 'qr'


def test_certificate_service_normalize_template_payload_uses_configured_fixed_defaults(app):
    with app.app_context():
        app.config['CERTIFICATE_QR_DEFAULT_X_MM'] = 12
        app.config['CERTIFICATE_QR_DEFAULT_Y_MM'] = 108
        app.config['CERTIFICATE_QR_DEFAULT_SIZE_MM'] = 36
        app.config['CERTIFICATE_HASH_DEFAULT_X_MM'] = 12
        app.config['CERTIFICATE_HASH_DEFAULT_Y_MM'] = 150
        app.config['CERTIFICATE_DATE_DEFAULT_X_MM'] = 12
        app.config['CERTIFICATE_DATE_DEFAULT_Y_MM'] = 195
        app.config['CERTIFICATE_NAME_DEFAULT_X_MM'] = 30
        app.config['CERTIFICATE_NAME_DEFAULT_Y_MM'] = 65
        app.config['CERTIFICATE_NAME_DEFAULT_W_MM'] = 240
        app.config['CERTIFICATE_NAME_DEFAULT_H_MM'] = 12
        app.config['CERTIFICATE_NAME_DEFAULT_FONT_SIZE'] = 24

        expected = {
            item['id']: item
            for item in CertificateService.get_fixed_validation_elements()
        }
        normalized = CertificateService.normalize_template_payload({
            'version': 2,
            'document': {'gridSize': 2, 'snap': True, 'guides': True},
            'elements': [],
        })
        by_id = {item['id']: item for item in normalized['elements']}

        for item_id in ('name_fixed', 'date_fixed', 'hash', 'qrcode'):
            assert by_id[item_id]['x'] == pytest.approx(expected[item_id]['x'])
            assert by_id[item_id]['y'] == pytest.approx(expected[item_id]['y'])
            assert by_id[item_id]['w'] == pytest.approx(expected[item_id]['w'])
            assert by_id[item_id]['h'] == pytest.approx(expected[item_id]['h'])

        assert by_id['name_fixed']['font'] == pytest.approx(expected['name_fixed']['font'])
        assert by_id['qrcode']['size'] == expected['qrcode']['size']


def test_certificate_service_normalize_template_payload_uses_recipient_name_in_institutional_mode():
    normalized = CertificateService.normalize_template_payload({
        'version': 2,
        'document': {'gridSize': 2, 'snap': True, 'guides': True},
        'elements': [],
    }, designer_mode='institutional')

    by_id = {item['id']: item for item in normalized['elements']}

    assert by_id['name_fixed']['text'] == '{{RECIPIENT_NAME}}'


def test_certificate_service_build_template_tags_uses_generation_date_for_issue_date(monkeypatch):
    monkeypatch.setattr(
        'app.services.certificate_service.current_certificate_issue_date_label',
        lambda: '15/03/2026',
    )
    service = CertificateService()
    event = SimpleNamespace(nome='Evento Teste', data_inicio=date(2030, 1, 10))
    user = SimpleNamespace(nome='Aluno Teste', cpf='12345678900')

    tags = service._build_template_tags(
        event,
        user,
        [],
        '4 horas',
        tag_overrides={
            '{{DATA}}': '01/01/2000',
            '{{EMISSION_DATE}}': '01/01/2000',
        },
    )

    assert tags['{{DATA}}'] == '15/03/2026'
    assert tags['{{EMISSION_DATE}}'] == '15/03/2026'


def test_certificate_service_build_template_tags_exposes_reference_date_for_event_or_activity(monkeypatch):
    monkeypatch.setattr(
        'app.services.certificate_service.current_certificate_issue_date_label',
        lambda: '15/03/2026',
    )
    service = CertificateService()
    event = SimpleNamespace(nome='Evento Teste', data_inicio=date(2030, 1, 10))
    user = SimpleNamespace(nome='Aluno Teste', cpf='12345678900')
    activity = SimpleNamespace(nome='Oficina', palestrante='Prof. Teste', data_atv=date(2030, 1, 12))

    tags_with_activity = service._build_template_tags(event, user, [activity], '4 horas')
    tags_without_activity = service._build_template_tags(event, user, [], '4 horas')

    assert tags_with_activity['{{DATA_REALIZACAO}}'] == '12/01/2030'
    assert tags_without_activity['{{DATA_REALIZACAO}}'] == '10/01/2030'


def test_certificate_service_build_template_tags_exposes_plural_speakers(monkeypatch):
    monkeypatch.setattr(
        'app.services.certificate_service.current_certificate_issue_date_label',
        lambda: '15/03/2026',
    )
    service = CertificateService()
    event = SimpleNamespace(nome='Evento Teste', data_inicio=date(2030, 1, 10))
    user = SimpleNamespace(nome='Aluno Teste', cpf='12345678900')
    activity = SimpleNamespace(
        nome='Oficina',
        palestrante='Prof. Principal',
        palestrantes=[
            {'nome': 'Prof. Principal', 'email': 'principal@example.com', 'ordem': 0},
            {'nome': 'Convidada Especial', 'email': 'convidada@example.com', 'ordem': 1},
        ],
        data_atv=date(2030, 1, 12),
    )

    tags = service._build_template_tags(event, user, [activity], '4 horas')

    assert tags['{{PALESTRANTE}}'] == 'Prof. Principal'
    assert tags['{{PALESTRANTES}}'] == 'Prof. Principal, Convidada Especial'


def test_institutional_certificate_service_generate_recipient_pdf_injects_default_recipient_tags(monkeypatch):
    monkeypatch.setattr(
        'app.services.institutional_certificate_service.current_certificate_issue_date_label',
        lambda: '15/03/2026',
    )
    service = InstitutionalCertificateService()
    captured = {}

    def fake_generate_pdf(event, user, activities, total_hours, enrollment=None, template_override=None, tag_overrides=None):
        captured['event'] = event
        captured['user'] = user
        captured['tag_overrides'] = dict(tag_overrides or {})
        return 'mocked.pdf'

    monkeypatch.setattr(service.event_certificate_service, 'generate_pdf', fake_generate_pdf)

    certificate = SimpleNamespace(
        id=10,
        titulo='Certificado Institucional',
        categoria='Reconhecimento',
        data_emissao='2030-01-10',
        signer_name='Coord. NUTED',
        cert_bg_path='',
        cert_template_json=json.dumps({
            'version': 2,
            'document': {'gridSize': 2, 'snap': True, 'guides': True},
            'elements': [
                {'id': 'name_fixed', 'type': 'text', 'text': '{{RECIPIENT_NAME}}'},
            ],
        }),
    )
    recipient = SimpleNamespace(
        id=5,
        nome='Maria da Silva',
        email='maria@example.com',
        cpf='12345678900',
        cert_hash='HASH1234567890AB',
        metadata_json=json.dumps({'carga_horaria': '12 horas', 'curso_usuario': 'Direito'}),
        linked_user=None,
    )

    pdf_path = service.generate_recipient_pdf(certificate, recipient)

    assert pdf_path == 'mocked.pdf'
    assert captured['tag_overrides']['{{RECIPIENT_NAME}}'] == 'Maria da Silva'
    assert captured['tag_overrides']['{{NOME}}'] == 'Maria da Silva'
    assert captured['tag_overrides']['{{CERTIFICATE_TITLE}}'] == 'Certificado Institucional'
    assert captured['tag_overrides']['{{EMISSION_DATE}}'] == '15/03/2026'
    assert captured['tag_overrides']['{{DATA}}'] == '15/03/2026'
    assert captured['tag_overrides']['{{DATA_REALIZACAO}}'] == ''
    assert captured['tag_overrides']['{{CARGA_HORARIA}}'] == '12 horas'
    assert captured['tag_overrides']['{{CURSO_USUARIO}}'] == 'Direito'
    assert captured['tag_overrides']['{{HASH}}'] == 'HASH1234567890AB'


def test_certificate_service_parse_template_elements_restores_default_institutional_content_when_only_fixed_elements():
    service = CertificateService()
    fake_certificate = SimpleNamespace(
        cert_template_json=json.dumps({
            'version': 2,
            'document': {'gridSize': 2, 'snap': True, 'guides': True},
            'elements': CertificateService.get_fixed_validation_elements(designer_mode='institutional'),
        }),
        cert_bg_path='',
        designer_mode='institutional',
        is_institutional_certificate=True,
    )

    elements, background = service._parse_template_elements(fake_certificate)
    by_id = {item['id']: item for item in elements}

    assert background == ''
    assert 'txt2' in by_id
    assert by_id['txt2']['text'] == 'Certificamos que {{RECIPIENT_NAME}} participou como {{CATEGORY}} do curso {{CURSO_USUARIO}}, com carga horária de {{CARGA_HORARIA}} horas.'


def test_certificate_service_generate_pdf_template_override_keeps_fixed_element_geometry(app, admin_user):
    with app.app_context():
        output_dir = os.path.join(app.root_path, 'static', 'certificates', 'generated')
        os.makedirs(output_dir, exist_ok=True)

        event = Event(
            owner_username='admin_test',
            nome='Evento Layout Override',
            descricao='Teste geometria',
            tipo='RAPIDO',
            data_inicio=date(2030, 8, 12),
            hora_inicio=time(8, 0),
        )
        user = User(
            username='cert_user_override',
            role='student',
            nome='Aluno Override',
            cpf='10000000004',
            email='override@example.com'
        )
        user.set_password('1234')

        db.session.add(event)
        db.session.add(user)
        db.session.commit()

        template_override = {
            'version': 2,
            'document': {'gridSize': 2, 'snap': True, 'guides': True},
            'elements': [
                {'id': 'hash', 'type': 'text', 'text': '{{HASH}}', 'x': 17, 'y': 71, 'w': 18, 'h': 4, 'font': 16},
                {'id': 'date_fixed', 'type': 'text', 'text': 'Data de Emissão: {{DATA}}', 'x': 16, 'y': 82, 'w': 25, 'h': 4, 'font': 11},
                {'id': 'qrcode', 'type': 'qr', 'x': 22, 'y': 33, 'w': 11, 'h': 11},
            ],
        }

        captured = {}
        service = CertificateService()

        def capture_qr(pdf_canvas, config, page_width, page_height, validation_url):
            captured['qrcode'] = dict(config)

        def capture_text(pdf_canvas, config, page_width, page_height, tags):
            captured.setdefault('text', {})[config['id']] = dict(config)

        service._draw_qr_element = capture_qr
        service._draw_text_element = capture_text

        pdf_path = service.generate_pdf(
            event,
            user,
            activities=[],
            total_hours=10,
            template_override=template_override,
            tag_overrides={'{{HASH}}': 'OVERRIDEHASH1234'},
        )

        assert os.path.exists(pdf_path)
        assert captured['qrcode']['x'] == pytest.approx(22)
        assert captured['qrcode']['y'] == pytest.approx(33)
        assert captured['qrcode']['w'] == pytest.approx(11)
        assert captured['qrcode']['h'] == pytest.approx(11)
        assert captured['text']['hash']['x'] == pytest.approx(17)
        assert captured['text']['hash']['y'] == pytest.approx(71)
        assert captured['text']['hash']['w'] == pytest.approx(18)
        assert captured['text']['date_fixed']['x'] == pytest.approx(16)
        assert captured['text']['date_fixed']['y'] == pytest.approx(82)


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
