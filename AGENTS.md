# Repository Instructions

## Project Shape
- Flask app for academic event management. `run.py` imports `create_app()`; `app/__init__.py` wires extensions, blueprints, and CLI commands.
- API blueprints live in `app/api/`; page routes live in `app/main/routes.py`; business logic is in `app/services/`; data helpers are in `app/repositories/`; SQLAlchemy models are centralized in `app/models.py`.
- UI is server-rendered Jinja plus Bootstrap/static JS in `app/templates/` and `app/static/css/style.css`; keep user-facing labels/messages in Portuguese.
- Identity is CPF-centric: `normalize_cpf()` strips formatting, `CPFDigitsType` stores 11 digits, and participant usernames are normalized CPFs. Do not compare formatted CPF strings.

## Commands
- Install dependencies: `python -m pip install -r requirements.txt`. This is the only dependency manifest; there is no lockfile or task runner.
- Commands in docs use `python`/`flask`; in bare Linux shells without a venv, use `python3` and `python3 -m flask` if those aliases are missing or broken.
- Run the app: `python run.py` at `http://localhost:5000`.
- Run the email worker: `python worker.py`.
- Apply migrations: `flask --app run.py db upgrade`.
- Seed local users: `flask --app run.py seed-dev-data`.
- Bootstrap PostgreSQL schema only: `flask --app run.py bootstrap-postgres --skip-data`; include legacy SQLite data with `flask --app run.py bootstrap-postgres` or `python scripts/migrate_sqlite_to_postgres.py --target-uri "postgresql+psycopg://..."`.
- Full tests: `python -m pytest -q`.
- Focused test: `python -m pytest tests/test_api.py::test_name -q`.
- Format/lint: `python -m black .`, `python -m black --check .`, and `python -m flake8 .` using 120-char lines with E203/W503 ignored. No typecheck task is configured.

## Environment And Data
- `config.py` manually loads root `.env`; `DATABASE_URL` overrides `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`.
- Normal app config targets PostgreSQL; `TestConfig` uses in-memory SQLite, so routine `pytest` does not require PostgreSQL.
- `RABBITMQ_URL` defaults to `amqp://guest:guest@localhost:5672/`; repo docs often use port `7770` for Docker/remote access. AMQP is direct TCP, not `https://.../rabbitmq/`.
- `BASE_URL` plus optional `BASE_PATH` must be respected for external links; use `build_absolute_app_url()` for QR, email, certificate, and password-reset URLs.

## Tests And Script Gotchas
- `pytest.ini` sets `testpaths = tests`; root `test_email_templates.py` is a live RabbitMQ publisher to `nuted-ia.dev:7770`, not routine test coverage.
- Docs mention `flask --app run.py tutorial-reset --yes`, but current `app/cli.py` only registers `init-db`, `seed-dev-data`, and `bootstrap-postgres`.
- The executable tutorial path is `python tutorial/run_tutorial.py`. Without `--skip-reset`, it calls `reset_tutorial_database()`, drops/recreates the configured DB, and writes `tutorial/tutorial.md` plus `tutorial/screenshots/`.
- If changing models, add or adjust Alembic migrations under `migrations/versions/` and verify with `flask --app run.py db upgrade`.
- README notes the `event_responsibles` migration may require `scripts/grant_event_responsibles_privileges.sql` if migrations were applied as the `postgres` superuser.

## Domain Conventions
- Event ownership now lives in `Event.responsibles`/`EventResponsible` with exactly one `is_primary`; `Event.owner_username` mirrors the primary responsible for compatibility.
- Flask publishes notification jobs through `NotificationService` to `email_queue`; `worker.py` declares `email_queue`, DLX, and `email_dlq`. Producers should not redeclare the queue.
- Moodle AVA integration is LTI 1.0/1.1: login button `GET /api/ava`, launch `POST /api/ava/launch`, CPF from `MOODLE_CPF_FIELD` or `username`; LTI 1.3 OIDC registration is intentionally rejected.
- Generated/local state is ignored: `.env`, venvs, logs, `app/static/certificates/`, and `gunicorn.pid`. Do not commit secrets or generated certificate files unless they are already intentionally tracked.
