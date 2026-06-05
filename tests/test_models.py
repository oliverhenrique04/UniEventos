from datetime import date, time

from sqlalchemy import text

from app.extensions import db
from app.models import Activity, Event, EventTeamCertificateRecipient, User


def test_user_password_hashing():
    u = User(username='test')
    u.set_password('cat')
    assert u.check_password('cat')
    assert not u.check_password('dog')


def test_user_to_dict():
    u = User(username='user', role='admin', nome='Test', cpf='12345678901')
    d = u.to_dict()
    assert d['username'] == 'user'
    assert d['role'] == 'admin'
    assert d['cpf'] == '12345678901'


def test_event_team_certificate_recipient_relationship(app, admin_user):
    with app.app_context():
        event = Event(
            owner_username='admin_test',
            nome='Evento Equipe',
            descricao='Evento para certificado de equipe',
            tipo='PADRAO',
            data_inicio=date(2030, 3, 1),
            hora_inicio=time(8, 0),
        )
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            nome='Oficina de Extensao',
            data_atv=date(2030, 3, 2),
            hora_atv=time(9, 0),
            carga_horaria=4,
            vagas=30,
        )
        db.session.add(activity)
        db.session.flush()

        recipient = EventTeamCertificateRecipient(
            event_id=event.id,
            activity_id=activity.id,
            nome='Facilitadora Teste',
            email='facilitadora@test.local',
            cpf='12345678901',
            role_label='Facilitador',
            workload_hours='4',
            source='manual',
        )
        db.session.add(recipient)
        db.session.commit()

        saved = EventTeamCertificateRecipient.query.filter_by(event_id=event.id).one()
        assert saved.event.nome == 'Evento Equipe'
        assert saved.activity.nome == 'Oficina de Extensao'
        assert saved.cpf == '12345678901'
        assert event.team_certificate_recipients[0].role_label == 'Facilitador'
        assert event.cert_team_bg_path == 'file/fundo_padrao.png'


def test_event_team_certificate_recipient_db_default_sets_delivery_false(app, admin_user):
    with app.app_context():
        event = Event(
            owner_username='admin_test',
            nome='Evento Equipe Raw Default',
            descricao='Evento para default do banco',
            tipo='PADRAO',
            data_inicio=date(2030, 3, 5),
            hora_inicio=time(8, 0),
        )
        db.session.add(event)
        db.session.flush()

        db.session.execute(
            text(
                """
                INSERT INTO event_team_certificate_recipients (
                    event_id,
                    activity_id,
                    nome,
                    email,
                    role_label,
                    source,
                    source_key
                ) VALUES (
                    :event_id,
                    NULL,
                    :nome,
                    :email,
                    :role_label,
                    :source,
                    :source_key
                )
                """
            ),
            {
                'event_id': event.id,
                'nome': 'Equipe Banco',
                'email': 'equipe.banco@test.local',
                'role_label': 'Equipe organizadora',
                'source': 'manual',
                'source_key': 'manual:raw-default',
            },
        )
        db.session.commit()

        saved = EventTeamCertificateRecipient.query.filter_by(source_key='manual:raw-default').one()
        assert saved.cert_entregue is False
