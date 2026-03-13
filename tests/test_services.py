import pytest
import json
import os
from datetime import date, time
from app.services.auth_service import AuthService
from app.services.event_service import EventService
from app.services.certificate_service import CertificateService
from app.models import User
from app.extensions import db
from app.models import Event

def test_auth_service_register(app):
    service = AuthService()
    data = {'username': 'newuser', 'password': '123', 'nome': 'New', 'cpf': '999'}
    user = service.register_user(data)
    assert user.username == 'newuser'
    assert user.check_password('123')

def test_auth_service_duplicate(app, admin_user):
    service = AuthService()
    data = {'username': 'admin_test', 'password': '123', 'nome': 'New', 'cpf': '999'}
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
