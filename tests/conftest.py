import pytest
from app import create_app, db
from config import TestConfig
from app.models import User

@pytest.fixture
def app():
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def admin_user(app):
    with app.app_context():
        user = User(username='admin_test', role='admin', nome='Admin Test', cpf='000')
        user.set_password('1234')
        db.session.add(user)
        db.session.commit()
        return user
