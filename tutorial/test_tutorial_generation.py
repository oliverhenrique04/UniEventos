import json
import pathlib

from app import create_app, db
from app.models import User
from app.services.auth_service import AuthService
from config import TestConfig
from tutorial.generate_participant_tutorial import (
    build_reset_password_token,
    get_capture_plan,
    load_settings,
    render_markdown,
)


def test_load_settings_falls_back_to_seed_defaults(tmp_path):
    settings = load_settings(config_path=tmp_path / "missing.json", base_url="http://127.0.0.1:5000")

    assert settings["base_url"] == "http://127.0.0.1:5000"
    assert settings["participant"]["cpf"] == "444.555.666-77"
    assert settings["participant"]["password"] == "1234"


def test_load_settings_accepts_real_participant_config(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "http://localhost:6000",
                "participant": {
                    "cpf": "123.456.789-00",
                    "password": "segredo",
                },
            }
        ),
        encoding="utf-8",
    )

    settings = load_settings(config_path=config_path)

    assert settings["base_url"] == "http://localhost:6000"
    assert settings["participant"]["cpf"] == "123.456.789-00"
    assert settings["participant"]["password"] == "segredo"


def test_load_settings_ignores_legacy_username_that_is_not_a_cpf(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "participante": {
                    "username": "user0001",
                    "password": "segredo-antigo",
                },
            }
        ),
        encoding="utf-8",
    )

    settings = load_settings(config_path=config_path)

    assert settings["participant"]["cpf"] == "444.555.666-77"
    assert settings["participant"]["password"] == "segredo-antigo"


def test_capture_plan_is_deterministic_and_participant_only():
    plan = get_capture_plan()

    assert len(plan) == 18
    assert [item.filename for item in plan][:4] == [
        "01_login.png",
        "02_cadastro.png",
        "03_recuperacao_senha.png",
        "04_resetar_senha.png",
    ]
    assert plan[-1].title == "Presença Confirmada"


def test_build_reset_password_token_targets_expected_user():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        user = User(
            username="aluno.demo",
            role="participante",
            nome="Aluno Demo",
            cpf="44455566677",
            email="aluno.demo@unieuro.edu.br",
        )
        user.set_password("1234")
        db.session.add(user)
        db.session.commit()

        token = build_reset_password_token(app, "aluno.demo")
        payload = AuthService()._password_reset_serializer().loads(
            token,
            max_age=AuthService()._password_reset_max_age(),
        )

        assert payload["username"] == "aluno.demo"


def test_render_markdown_creates_human_readable_tutorial(tmp_path, monkeypatch):
    import tutorial.generate_participant_tutorial as tutorial_module

    base_dir = tmp_path / "tutorial"
    screenshots_dir = base_dir / "screenshots"
    screenshots_dir.mkdir(parents=True)
    markdown_path = base_dir / "tutorial.md"
    screenshot_path = screenshots_dir / "01_login.png"
    screenshot_path.write_bytes(b"fake-image")

    monkeypatch.setattr(tutorial_module, "BASE_DIR", base_dir)
    monkeypatch.setattr(tutorial_module, "MARKDOWN_PATH", markdown_path)

    settings = {
        "participant": {
            "cpf": "444.555.666-77",
            "password": "1234",
        }
    }
    render_markdown(
        entries=[(get_capture_plan()[0], screenshot_path)],
        generated_at=tutorial_module.datetime(2026, 3, 14, tzinfo=tutorial_module.timezone.utc),
        settings=settings,
    )

    content = markdown_path.read_text(encoding="utf-8")
    assert "Tutorial Canônico do Participante" in content
    assert "screenshots/01_login.png" in content
    assert "444.555.666-77" in content
