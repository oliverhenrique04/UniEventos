import json

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
