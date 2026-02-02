import unittest
import json
import os
import sys

# Add project root to path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Event
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class SystemTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Create Users directly for testing
        u_admin = User(username='admin', role='admin', nome='Admin Teste', cpf='000.000.000-00')
        u_admin.set_password('admin')
        
        u_prof = User(username='prof', role='professor', nome='Prof Teste', cpf='111.111.111-11')
        u_prof.set_password('1234')

        db.session.add_all([u_admin, u_prof])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, username, password):
        return self.client.post('/api/login', json={
            'username': username,
            'password': password
        })

    def test_auth_flow(self):
        print("\n[TEST] Autenticação...")
        # Fail login
        res = self.login('admin', 'wrongpass')
        self.assertEqual(res.status_code, 401)
        
        # Success login
        res = self.login('admin', 'admin')
        self.assertEqual(res.status_code, 200)
        print(" -> Login OK")

    def test_create_and_list_event(self):
        print("\n[TEST] Criação de Eventos...")
        self.login('prof', '1234')
        
        # Create Event
        payload = {
            "nome": "Semana de TI",
            "descricao": "Evento Tech",
            "is_rapido": False,
            "data_inicio": "2026-10-10",
            "hora_inicio": "08:00",
            "data_fim": "2026-10-12",
            "hora_fim": "18:00",
            "atividades": [
                {
                    "nome": "Palestra AI",
                    "palestrante": "Gemini",
                    "local": "Auditorio",
                    "descricao": "Intro to AI",
                    "data_atv": "2026-10-10",
                    "hora_atv": "09:00",
                    "horas": 2,
                    "vagas": 50
                }
            ]
        }
        res = self.client.post('/api/criar_evento', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("mensagem", data)
        print(" -> Evento Criado OK")

        # List Events
        res = self.client.get('/api/eventos')
        self.assertEqual(res.status_code, 200)
        events = res.get_json()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['nome'], "Semana de TI")
        print(" -> Listagem OK")

    def test_pages_load(self):
        print("\n[TEST] Carregamento de Páginas...")
        # Redirect to login if not auth
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200) 
        # Note: Render template returns 200, but content differs based on auth. 
        # Since logic handles auth inside index route (if not current_user.is_authenticated return login_register.html)
        # It should always return 200 HTML.
        self.assertIn(b'UniEventos', res.data)
        print(" -> Index/Login Page OK")

if __name__ == '__main__':
    unittest.main()
