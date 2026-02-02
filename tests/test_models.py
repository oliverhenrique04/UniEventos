from app.models import User

def test_user_password_hashing():
    u = User(username='test')
    u.set_password('cat')
    assert u.check_password('cat')
    assert not u.check_password('dog')

def test_user_to_dict():
    u = User(username='user', role='admin', nome='Test', cpf='123')
    d = u.to_dict()
    assert d['username'] == 'user'
    assert d['role'] == 'admin'
    assert d['cpf'] == '123'
