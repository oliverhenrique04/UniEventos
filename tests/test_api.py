import json
from datetime import date, time
from app.models import Event
from app.extensions import db


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
        db.session.commit()
        return event.id

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


def test_upload_asset_requires_file(client, app, admin_user):
    _login_admin(client)
    event_id = _create_event_for_certs(app)

    res = client.post(f'/api/certificates/upload_asset/{event_id}', data={})
    assert res.status_code == 400
    assert 'Arquivo não enviado' in res.json['erro']
