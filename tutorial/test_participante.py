import pytest

from app import create_app, db
from app.models import Activity, Enrollment, Event, User
from app.tutorial_setup import TUTORIAL_COORDINATES, reset_tutorial_database
from app.utils import gerar_hash_dinamico
from config import TestConfig


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


def test_tutorial_reset_requires_explicit_confirmation(runner):
    result = runner.invoke(args=["tutorial-reset"])

    assert result.exit_code != 0
    assert "--yes" in result.output


def test_tutorial_reset_recreates_expected_dataset(runner, app):
    with app.app_context():
        ghost = User(username="ghost", role="participante", nome="Ghost", cpf="12312312312")
        ghost.set_password("1234")
        db.session.add(ghost)
        db.session.commit()

    result = runner.invoke(args=["tutorial-reset", "--yes"])

    assert result.exit_code == 0
    assert "6 usuarios" in result.output

    with app.app_context():
        assert User.query.count() == 6
        assert Event.query.count() == 1
        assert Activity.query.count() == 2
        assert Enrollment.query.count() == 1

        student = User.query.filter_by(username="aluno.demo").first()
        assert student is not None
        assert student.role == "participante"

        initial_enrollment = Enrollment.query.first()
        assert initial_enrollment.presente is True
        assert initial_enrollment.cert_hash is not None


def test_participant_smoke_flow_covers_enrollment_presence_and_history(client, app):
    with app.app_context():
        summary = reset_tutorial_database()
        scenario = summary["scenario"]
        activity_id = scenario["activity_checkin_id"]
        event_id = scenario["event_id"]
        event_token = scenario["event_token"]

    login_response = client.post(
        "/api/login",
        json={"cpf": "444.555.666-77", "password": "1234"},
    )
    assert login_response.status_code == 200

    event_page = client.get(f"/inscrever/{event_token}")
    assert event_page.status_code == 200

    enrollment_response = client.post(
        "/api/toggle_inscricao",
        json={"activity_id": activity_id, "acao": "inscrever"},
    )
    assert enrollment_response.status_code == 200

    with app.app_context():
        pending_enrollment = Enrollment.query.filter_by(activity_id=activity_id).first()
        assert pending_enrollment is not None
        assert pending_enrollment.presente is False
        checkin_hash = gerar_hash_dinamico(activity_id)

    checkin_page = client.get(f"/confirmar_presenca/{activity_id}/{checkin_hash}")
    assert checkin_page.status_code == 200

    presence_response = client.post(
        "/api/validar_presenca",
        json={
            "token": f"CHECKIN:{event_id}:{activity_id}:{checkin_hash}",
            "latitude": TUTORIAL_COORDINATES["latitude"],
            "longitude": TUTORIAL_COORDINATES["longitude"],
        },
    )
    assert presence_response.status_code == 200
    assert presence_response.get_json()["status"] == "success"

    history_page = client.get("/meus_eventos")
    profile_page = client.get("/perfil")
    assert history_page.status_code == 200
    assert profile_page.status_code == 200

    certificates = client.get("/api/me/history?type=certificates")
    activities = client.get("/api/me/history?type=activities")

    assert certificates.status_code == 200
    assert activities.status_code == 200

    certificate_payload = certificates.get_json()
    activities_payload = activities.get_json()
    assert len(certificate_payload["items"]) >= 1
    assert any(item["event_nome"] == "Evento Tutorial do Participante" for item in certificate_payload["items"])
    assert len(activities_payload["items"]) == 2
