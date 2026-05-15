import importlib.util
from datetime import date, time
from pathlib import Path

import pytest
from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Course, Event, EventResponsible, User
from app.repositories.event_repository import EventRepository
from app.serializers import serialize_event
from app.services.event_service import EventService


def _load_event_responsibles_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / 'migrations'
        / 'versions'
        / 'a5b7c9d2e4f6_add_event_responsibles.py'
    )
    spec = importlib.util.spec_from_file_location(
        'event_responsibles_migration',
        migration_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _persist_user(
    username,
    role='professor',
    cpf='90000000000',
    can_create_events=False,
    nome=None,
    email=None,
):
    user = User(
        username=username,
        role=role,
        nome=nome or username.replace('_', ' ').title(),
        cpf=cpf,
        email=email,
        can_create_events=can_create_events,
    )
    user.set_password('1234')
    db.session.add(user)
    db.session.flush()
    return user


def _persist_course(nome):
    course = Course(nome=nome)
    db.session.add(course)
    db.session.flush()
    return course


def _responsible_state(event):
    return [
        (responsible.user_username, bool(responsible.is_primary))
        for responsible in event.responsibles
    ]


def _event_payload(**overrides):
    payload = {
        'nome': 'Evento Co Responsavel',
        'descricao': 'Evento usado nos testes de co-responsaveis',
        'is_rapido': True,
        'carga_horaria_rapida': 2,
        'data_inicio': '2030-05-04',
        'hora_inicio': '10:00',
        'data_fim': '2030-05-04',
        'hora_fim': '12:00',
    }
    payload.update(overrides)
    return payload


def test_event_responsible_model_links_event_and_user(app):
    owner = _persist_user(
        'model_owner_resp',
        role='professor',
        cpf='90000000001',
        can_create_events=True,
        nome='Responsavel Modelo',
    )
    event = Event(
        owner_username=owner.username,
        nome='Evento Modelo Responsavel',
        descricao='Desc',
        tipo='PADRAO',
        data_inicio=date(2030, 5, 4),
        hora_inicio=time(10, 0),
        data_fim=date(2030, 5, 4),
        hora_fim=time(12, 0),
    )
    event.responsibles.append(EventResponsible(user=owner, is_primary=True))

    db.session.add(event)
    db.session.commit()

    saved_event = db.session.get(Event, event.id)
    assert _responsible_state(saved_event) == [('model_owner_resp', True)]
    assert saved_event.responsibles[0].user.nome == 'Responsavel Modelo'
    assert owner.event_responsibilities[0].event_id == saved_event.id


def test_event_responsible_model_rejects_two_primary_responsibles_for_same_event(app):
    owner = _persist_user(
        'primary_owner_resp',
        role='professor',
        cpf='90000000002',
        can_create_events=True,
    )
    co_owner = _persist_user(
        'primary_co_owner_resp',
        role='coordenador',
        cpf='90000000003',
        can_create_events=True,
    )
    event = Event(
        owner_username=owner.username,
        nome='Evento Com Dois Primarios',
        descricao='Desc',
        tipo='PADRAO',
        data_inicio=date(2030, 5, 4),
        hora_inicio=time(10, 0),
        data_fim=date(2030, 5, 4),
        hora_fim=time(12, 0),
    )
    event.responsibles.extend(
        [
            EventResponsible(user=owner, is_primary=True),
            EventResponsible(user=co_owner, is_primary=True),
        ]
    )

    db.session.add(event)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()


def test_event_responsibles_migration_rejects_events_without_owner_username():
    migration = _load_event_responsibles_migration_module()

    with pytest.raises(RuntimeError, match=r'events without owner_username found: \[10, 20\]'):
        migration._raise_for_events_without_owner([10, 20])


def test_event_service_create_event_syncs_primary_and_co_responsible(app):
    owner = _persist_user(
        'service_owner_resp',
        role='professor',
        cpf='90000000010',
        can_create_events=True,
    )
    co_responsible = _persist_user(
        'service_co_resp',
        role='admin',
        cpf='90000000011',
        can_create_events=False,
    )
    service = EventService()

    event = service.create_event(owner.username, _event_payload(
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            co_responsible.username,
        ]
    ))

    saved_event = db.session.get(Event, event.id)
    assert _responsible_state(saved_event) == [
        ('service_owner_resp', True),
        ('service_co_resp', False),
    ]
    assert saved_event.owner_username == owner.username


def test_event_service_create_event_defaults_owner_as_primary_responsible(app):
    owner = _persist_user(
        'service_owner_default',
        role='professor',
        cpf='90000000012',
        can_create_events=True,
    )
    service = EventService()

    event = service.create_event(owner.username, _event_payload())

    saved_event = db.session.get(Event, event.id)
    assert _responsible_state(saved_event) == [('service_owner_default', True)]
    assert saved_event.owner_username == owner.username


def test_event_service_create_event_rejects_explicit_empty_responsibles_list(app):
    owner = _persist_user(
        'service_owner_empty_list',
        role='professor',
        cpf='90000000012',
        can_create_events=True,
    )
    service = EventService()

    with pytest.raises(ValueError) as exc_info:
        service.create_event(owner.username, _event_payload(responsaveis=[]))

    assert str(exc_info.value) == 'Informe ao menos um responsável pelo evento.'


def test_event_service_create_event_accepts_explicit_responsibles_without_readding_creator(app):
    owner = _persist_user(
        'service_owner_no_readd',
        role='professor',
        cpf='90000000025',
        can_create_events=True,
    )
    explicit_primary = _persist_user(
        'service_explicit_primary_only',
        role='admin',
        cpf='90000000026',
        can_create_events=False,
    )
    service = EventService()

    event = service.create_event(owner.username, _event_payload(
        responsaveis=[
            {'username': explicit_primary.username, 'is_primary': True},
        ]
    ))

    saved_event = db.session.get(Event, event.id)
    assert _responsible_state(saved_event) == [('service_explicit_primary_only', True)]
    assert saved_event.owner_username == explicit_primary.username


def test_event_service_update_event_switches_primary_responsible_and_owner_username(app):
    owner = _persist_user(
        'service_owner_update',
        role='admin',
        cpf='90000000013',
        can_create_events=False,
    )
    co_responsible = _persist_user(
        'service_co_update',
        role='admin',
        cpf='90000000014',
        can_create_events=False,
    )
    service = EventService()

    event = service.create_event(owner.username, _event_payload(
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': co_responsible.username, 'is_primary': False},
        ]
    ))

    updated_event, message = service.update_event(event.id, owner, _event_payload(
        nome='Evento Atualizado Com Novo Principal',
        responsaveis=[
            {'username': owner.username, 'is_primary': False},
            {'username': co_responsible.username, 'is_primary': True},
        ],
    ))

    saved_event = db.session.get(Event, event.id)
    assert updated_event is not None
    assert message == 'Evento atualizado com sucesso!'
    assert _responsible_state(saved_event) == [
        ('service_co_update', True),
        ('service_owner_update', False),
    ]
    assert saved_event.owner_username == co_responsible.username


def test_event_service_update_event_with_only_new_primary_removes_previous_owner_from_responsibles(app):
    owner = _persist_user(
        'service_owner_replace',
        role='professor',
        cpf='90000000019',
        can_create_events=True,
    )
    new_primary = _persist_user(
        'service_new_primary_replace',
        role='admin',
        cpf='90000000020',
        can_create_events=False,
    )
    service = EventService()

    event = service.create_event(owner.username, _event_payload(
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': new_primary.username, 'is_primary': False},
        ]
    ))

    updated_event, message = service.update_event(event.id, owner, _event_payload(
        nome='Evento Atualizado Sem Reanexar Owner',
        responsaveis=[
            {'username': new_primary.username, 'is_primary': True},
        ],
    ))

    saved_event = db.session.get(Event, event.id)
    assert updated_event is not None
    assert message == 'Evento atualizado com sucesso!'
    assert _responsible_state(saved_event) == [
        ('service_new_primary_replace', True),
    ]
    assert saved_event.owner_username == new_primary.username


def test_event_service_update_event_restores_owner_as_primary_for_legacy_event_without_responsibles(app):
    owner = _persist_user(
        'legacy_owner_update',
        role='professor',
        cpf='90000000015',
        can_create_events=True,
    )
    event = Event(
        owner_username=owner.username,
        nome='Evento Legado Sem Responsaveis',
        descricao='Desc',
        tipo='PADRAO',
        data_inicio=date(2030, 5, 4),
        hora_inicio=time(10, 0),
        data_fim=date(2030, 5, 4),
        hora_fim=time(12, 0),
    )
    db.session.add(event)
    db.session.commit()

    service = EventService()
    updated_event, message = service.update_event(event.id, owner, _event_payload(
        nome='Evento Legado Atualizado',
        is_rapido=False,
    ))

    saved_event = db.session.get(Event, event.id)
    assert updated_event is not None
    assert message == 'Evento atualizado com sucesso!'
    assert _responsible_state(saved_event) == [('legacy_owner_update', True)]
    assert saved_event.owner_username == owner.username


@pytest.mark.parametrize(
    ('raw_responsibles', 'expected_message'),
    [
        ('service_owner_validation', 'Informe a lista de responsáveis do evento.'),
        ([], 'Informe ao menos um responsável pelo evento.'),
        ([{'username': 'service_owner_validation', 'is_primary': False}], 'Selecione exatamente um responsável principal.'),
        ([
            {'username': 'service_owner_validation', 'is_primary': True},
            'service_owner_validation',
        ], 'Responsável duplicado: service_owner_validation.'),
        ([{'username': 'missing_responsible', 'is_primary': True}], 'Usuário responsável não encontrado: missing_responsible.'),
    ],
)
def test_event_service_normalize_event_responsibles_payload_validates_invalid_payloads(app, raw_responsibles, expected_message):
    _persist_user(
        'service_owner_validation',
        role='professor',
        cpf='90000000016',
        can_create_events=True,
    )
    service = EventService()

    with pytest.raises(ValueError) as exc_info:
        service._normalize_event_responsibles_payload(raw_responsibles)

    assert str(exc_info.value) == expected_message


def test_event_service_normalize_event_responsibles_payload_rejects_ineligible_user(app):
    _persist_user(
        'service_owner_eligible',
        role='professor',
        cpf='90000000017',
        can_create_events=True,
    )
    ineligible_user = _persist_user(
        'service_participant_ineligible',
        role='participante',
        cpf='90000000018',
        can_create_events=False,
    )
    service = EventService()

    with pytest.raises(ValueError) as exc_info:
        service._normalize_event_responsibles_payload([
            {'username': ineligible_user.username, 'is_primary': True},
        ])

    assert str(exc_info.value) == (
        'Usuário sem permissão para ser responsável pelo evento: '
        'service_participant_ineligible.'
    )


def test_event_service_create_event_rejects_extensao_without_can_create_events_as_responsible(app):
    owner = _persist_user(
        'service_owner_extensao_guard',
        role='professor',
        cpf='90000000021',
        can_create_events=True,
    )
    extension_user = _persist_user(
        'service_extensao_sem_criacao',
        role='extensao',
        cpf='90000000022',
        can_create_events=False,
    )
    service = EventService()

    with pytest.raises(ValueError) as exc_info:
        service.create_event(owner.username, _event_payload(
            responsaveis=[
                {'username': owner.username, 'is_primary': True},
                {'username': extension_user.username, 'is_primary': False},
            ]
        ))

    assert str(exc_info.value) == (
        'Usuário sem permissão para ser responsável pelo evento: '
        'service_extensao_sem_criacao.'
    )


def test_event_service_create_event_accepts_secondary_professor_with_can_create_events(app):
    owner = _persist_user(
        'service_owner_professor_primary',
        role='professor',
        cpf='90000000027',
        can_create_events=True,
    )
    secondary_professor = _persist_user(
        'service_professor_secondary',
        role='professor',
        cpf='90000000028',
        can_create_events=True,
    )
    service = EventService()

    event = service.create_event(owner.username, _event_payload(
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': secondary_professor.username, 'is_primary': False},
        ]
    ))

    saved_event = db.session.get(Event, event.id)
    assert _responsible_state(saved_event) == [
        ('service_owner_professor_primary', True),
        ('service_professor_secondary', False),
    ]
    assert saved_event.owner_username == owner.username


def test_event_service_create_event_rejects_coordinator_from_other_course_as_responsible(app):
    engineering_course = _persist_course('Engenharia de Software')
    law_course = _persist_course('Direito')
    owner = _persist_user(
        'service_owner_course_guard',
        role='professor',
        cpf='90000000023',
        can_create_events=True,
        nome='Owner Curso Guard',
    )
    owner.course_id = engineering_course.id
    foreign_coordinator = _persist_user(
        'service_coord_other_course',
        role='coordenador',
        cpf='90000000024',
        can_create_events=False,
        nome='Coordenador Outro Curso',
    )
    foreign_coordinator.course_id = law_course.id
    db.session.flush()
    service = EventService()

    with pytest.raises(ValueError) as exc_info:
        service.create_event(owner.username, _event_payload(
            curso=engineering_course.nome,
            responsaveis=[
                {'username': owner.username, 'is_primary': True},
                {'username': foreign_coordinator.username, 'is_primary': False},
            ]
        ))

    assert str(exc_info.value) == (
        'Usuário sem permissão para ser responsável pelo evento: '
        'service_coord_other_course.'
    )


def test_event_service_grants_co_responsible_same_operational_permissions_as_primary(app):
    owner = _persist_user(
        'service_owner_permissions',
        role='professor',
        cpf='90000000029',
        can_create_events=True,
    )
    co_responsible = _persist_user(
        'service_co_permissions',
        role='professor',
        cpf='90000000030',
        can_create_events=True,
    )
    service = EventService()

    event = service.create_event(owner.username, _event_payload(
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': co_responsible.username, 'is_primary': False},
        ]
    ))

    saved_event = db.session.get(Event, event.id)

    assert service.is_event_owner(owner, saved_event) is True
    assert service.is_event_owner(co_responsible, saved_event) is True
    assert service.can_view_event(owner, saved_event) is True
    assert service.can_view_event(co_responsible, saved_event) is True
    assert service.can_edit_event(owner, saved_event) is True
    assert service.can_edit_event(co_responsible, saved_event) is True
    assert service.can_delete_event(owner, saved_event) is True
    assert service.can_delete_event(co_responsible, saved_event) is True


def test_event_repository_and_creator_listings_include_events_for_co_responsible(app):
    owner = _persist_user(
        'service_owner_listings',
        role='professor',
        cpf='90000000031',
        can_create_events=True,
    )
    co_responsible = _persist_user(
        'service_co_listings',
        role='professor',
        cpf='90000000032',
        can_create_events=True,
    )
    outsider_owner = _persist_user(
        'service_outsider_listings',
        role='professor',
        cpf='90000000033',
        can_create_events=True,
    )
    service = EventService()
    repo = EventRepository()

    shared_event = service.create_event(owner.username, _event_payload(
        nome='Evento Compartilhado Listagem',
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': co_responsible.username, 'is_primary': False},
        ],
    ))
    service.create_event(outsider_owner.username, _event_payload(
        nome='Evento Sem Vinculo',
    ))

    repository_events = repo.get_by_owner(co_responsible.username)
    events_page = service.get_events_for_user_paginated(co_responsible, page=1, per_page=10)
    admin_page = service.list_events_paginated(co_responsible, page=1, per_page=10)

    assert [event.id for event in repository_events] == [shared_event.id]
    assert [event.id for event in events_page.items] == [shared_event.id]
    assert [event.id for event in admin_page.items] == [shared_event.id]


def test_event_repository_and_creator_listings_include_legacy_owner_without_responsibles(app):
    owner = _persist_user(
        'legacy_owner_listings',
        role='professor',
        cpf='90000000034',
        can_create_events=True,
    )
    outsider_owner = _persist_user(
        'legacy_outsider_listings',
        role='professor',
        cpf='90000000035',
        can_create_events=True,
    )
    service = EventService()
    repo = EventRepository()

    legacy_event = Event(
        owner_username=owner.username,
        nome='Evento Legado Owner Username',
        descricao='Evento criado diretamente sem responsaveis vinculados',
        tipo='PADRAO',
        data_inicio=date(2030, 5, 5),
        hora_inicio=time(9, 0),
        data_fim=date(2030, 5, 5),
        hora_fim=time(11, 0),
    )
    outsider_event = Event(
        owner_username=outsider_owner.username,
        nome='Evento Legado Externo',
        descricao='Evento sem relacao de responsaveis para outro usuario',
        tipo='PADRAO',
        data_inicio=date(2030, 5, 6),
        hora_inicio=time(9, 0),
        data_fim=date(2030, 5, 6),
        hora_fim=time(11, 0),
    )
    db.session.add_all([legacy_event, outsider_event])
    db.session.commit()

    saved_legacy_event = db.session.get(Event, legacy_event.id)
    assert saved_legacy_event is not None
    assert saved_legacy_event.responsibles == []

    repository_events = repo.get_by_owner(owner.username)
    events_page = service.get_events_for_user_paginated(owner, page=1, per_page=10)
    admin_page = service.list_events_paginated(owner, page=1, per_page=10)

    assert [event.id for event in repository_events] == [legacy_event.id]
    assert [event.id for event in events_page.items] == [legacy_event.id]
    assert [event.id for event in admin_page.items] == [legacy_event.id]


def test_serialize_event_returns_primary_and_full_responsibles_payload(app):
    owner = _persist_user(
        'serialize_owner_resp',
        role='professor',
        cpf='90000000038',
        can_create_events=True,
        nome='Responsavel Principal Serializado',
        email='principal.serialize@test.local',
    )
    co_responsible = _persist_user(
        'serialize_co_resp',
        role='admin',
        cpf='90000000039',
        can_create_events=False,
        nome='Corresponsavel Serializado',
        email='co.serialize@test.local',
    )
    service = EventService()
    service.notification_service.send_email_task = lambda **kwargs: True

    event = service.create_event(owner.username, _event_payload(
        nome='Evento Serializado Responsaveis',
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': co_responsible.username, 'is_primary': False},
        ],
    ))

    payload = serialize_event(db.session.get(Event, event.id))

    assert payload['owner'] == owner.username
    assert payload['owner_name'] == owner.nome
    assert payload['responsavel_principal'] == {
        'username': owner.username,
        'nome': owner.nome,
        'email': owner.email,
        'role': owner.role,
        'is_primary': True,
    }
    assert payload['responsaveis'] == [
        {
            'username': owner.username,
            'nome': owner.nome,
            'email': owner.email,
            'role': owner.role,
            'is_primary': True,
        },
        {
            'username': co_responsible.username,
            'nome': co_responsible.nome,
            'email': co_responsible.email,
            'role': co_responsible.role,
            'is_primary': False,
        },
    ]


def test_event_service_create_event_notifies_all_responsibles_with_email(app):
    owner = _persist_user(
        'notify_owner_resp',
        role='professor',
        cpf='90000000040',
        can_create_events=True,
        nome='Responsavel Principal Notificado',
        email='principal.notify@test.local',
    )
    co_responsible = _persist_user(
        'notify_co_resp',
        role='admin',
        cpf='90000000041',
        can_create_events=False,
        nome='Corresponsavel Notificado',
        email='co.notify@test.local',
    )
    no_email_responsible = _persist_user(
        'notify_no_email_resp',
        role='gestor',
        cpf='90000000042',
        can_create_events=False,
        nome='Responsavel Sem Email',
        email=None,
    )
    service = EventService()
    sent_payloads = []
    service.notification_service.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

    service.create_event(owner.username, _event_payload(
        nome='Evento Notifica Todos Responsaveis',
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': co_responsible.username, 'is_primary': False},
            {'username': no_email_responsible.username, 'is_primary': False},
        ],
    ))

    assert len(sent_payloads) == 2
    assert {payload['to_email'] for payload in sent_payloads} == {
        owner.email,
        co_responsible.email,
    }
    assert {payload['template_name'] for payload in sent_payloads} == {'event_created_owner.html'}


def test_list_events_paginated_owner_filter_finds_primary_and_co_responsible(app):
    admin = _persist_user(
        'service_admin_owner_filter',
        role='admin',
        cpf='90000000034',
        can_create_events=False,
    )
    owner = _persist_user(
        'service_owner_filter',
        role='professor',
        cpf='90000000035',
        can_create_events=True,
        nome='Responsavel Principal Filtro',
    )
    co_responsible = _persist_user(
        'service_co_filter',
        role='professor',
        cpf='90000000036',
        can_create_events=True,
        nome='Corresponsavel Nome Busca',
    )
    outsider_owner = _persist_user(
        'service_outsider_filter',
        role='professor',
        cpf='90000000037',
        can_create_events=True,
        nome='Responsavel Externo',
    )
    service = EventService()

    shared_event = service.create_event(owner.username, _event_payload(
        nome='Evento Compartilhado Filtro',
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': co_responsible.username, 'is_primary': False},
        ],
    ))
    service.create_event(outsider_owner.username, _event_payload(
        nome='Evento Externo Filtro',
    ))

    primary_page = service.list_events_paginated(admin, page=1, per_page=10, filters={'owner': owner.username})
    co_username_page = service.list_events_paginated(admin, page=1, per_page=10, filters={'owner': co_responsible.username})
    co_name_page = service.list_events_paginated(admin, page=1, per_page=10, filters={'owner': 'Nome Busca'})

    assert [event.id for event in primary_page.items] == [shared_event.id]
    assert [event.id for event in co_username_page.items] == [shared_event.id]
    assert [event.id for event in co_name_page.items] == [shared_event.id]


def test_event_service_create_notification_uses_base_path_links(app):
    with app.app_context():
        current_app.config['BASE_URL'] = 'https://portal.unieuro.br'
        current_app.config['BASE_PATH'] = '/unieventos'

        owner = _persist_user(
            'notify_base_path_owner',
            role='professor',
            cpf='90000000043',
            can_create_events=True,
            email='notify_base_path_owner@test.local',
        )
        service = EventService()
        sent_payloads = []
        service.notification_service.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

        service.create_event(owner.username, _event_payload(nome='Evento Base Path Notificacao'))

        assert len(sent_payloads) == 1
        template_data = sent_payloads[0]['template_data']
        assert template_data['event_link'].startswith('https://portal.unieuro.br/unieventos/inscrever/')
        assert template_data['manage_link'] == 'https://portal.unieuro.br/unieventos/eventos_admin'
