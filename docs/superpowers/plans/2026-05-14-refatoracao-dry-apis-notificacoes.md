# Refatoracao DRY de APIs e Notificacoes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remover duplicacoes de autorizacao, parsing de payload, fluxos AVA/importacao e montagem de contexto de notificacao sem quebrar contratos publicos existentes.

**Architecture:** A refatoracao sera incremental e orientada por testes. Primeiro entra uma camada fina de helpers de API para respostas JSON, autorizacao e leitura segura de payloads; depois a logica duplicada localizada em `admin.py`, `auth.py` e nos services sera extraida para funcoes privadas reutilizaveis, preservando rotas, status codes e chaves de resposta ja consumidas pelo frontend.

**Tech Stack:** Flask, Flask-Login, Flask-SQLAlchemy, Jinja2, pytest, monkeypatch.

---

## File Structure

- Create `app/api/helpers.py`: helpers compartilhados para `json_error`, `json_success`, `parse_json_body` e `admin_required`.
- Modify `app/api/courses.py`: trocar guardas inline e acesso direto a `request.json` pelos helpers compartilhados.
- Modify `app/api/admin.py`: reutilizar `admin_required`, leitura segura de JSON, validacao unica de upload e helpers genericos para jobs de importacao.
- Modify `app/api/auth.py`: extrair helpers privados para payload AVA/Moodle, validacao de credenciais LTI e autenticacao por payload.
- Modify `app/services/admin_service.py`: usar `build_absolute_app_url` para URLs de notificacao de inscricao manual.
- Modify `app/services/auth_service.py`: usar `build_absolute_app_url` e um helper privado de contexto base para e-mails de conta.
- Modify `app/services/event_service.py`: centralizar envio de e-mail para responsaveis e montagem de links/labels de evento.
- Modify `tests/conftest.py`: adicionar fixture simples para login/logout/troca de usuario em testes de API.
- Modify `tests/test_api.py`: cobrir regressao de JSON ausente, fluxo async XLSX, helpers AVA e parametrizacao de papeis no navbar/dashboard.
- Modify `tests/test_services.py`: cobrir URLs com `BASE_PATH` em notificacoes de auth/admin/eventos.
- Modify `tests/test_event_responsibles.py`: manter cobertura de notificacao de responsaveis e validar links absolutos quando aplicavel.

## Compatibility Rules

- Manter as rotas publicas e os payloads bem-sucedidos existentes.
- Manter a resposta `{"erro": "Negado"}` para negacao de acesso administrativo.
- Para payload JSON ausente ou invalido, padronizar retorno `400` com `{"erro": "Payload JSON obrigatório."}` ou `{"erro": "Payload JSON inválido."}` em vez de deixar excecoes vazarem.
- Em URLs enviadas por e-mail, passar a respeitar `BASE_PATH` via `build_absolute_app_url`, sem alterar o restante do conteudo dos templates.

---

### Task 1: Shared API Helpers And Safe JSON Parsing

**Files:**
- Create: `app/api/helpers.py`
- Modify: `app/api/courses.py`
- Modify: `app/api/admin.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing regression tests for missing JSON bodies**

Append to `tests/test_api.py`:

```python
def test_create_course_without_json_returns_structured_400(client, admin_user):
    _login_admin(client)

    res = client.post(
        '/api/courses/',
        data='',
        content_type='application/json',
    )

    assert res.status_code == 400
    assert res.is_json
    assert res.get_json() == {'erro': 'Payload JSON obrigatório.'}


def test_admin_update_permissions_without_json_returns_structured_400(client, admin_user):
    _login_admin(client)

    res = client.post(
        '/api/atualizar_permissoes',
        data='',
        content_type='application/json',
    )

    assert res.status_code == 400
    assert res.is_json
    assert res.get_json() == {'erro': 'Payload JSON obrigatório.'}
```

- [ ] **Step 2: Run the targeted API tests and verify they fail**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_create_course_without_json_returns_structured_400 tests/test_api.py::test_admin_update_permissions_without_json_returns_structured_400 -q
```

Expected: FAIL with `400` HTML/Flask default handling or an exception caused by direct access to `request.json` / `data.get(...)`.

- [ ] **Step 3: Add the shared API helper module and adopt it in the first endpoints**

Create `app/api/helpers.py`:

```python
from functools import wraps

from flask import jsonify, request
from flask_login import current_user


def json_error(message, status=400):
    return jsonify({'erro': message}), status


def json_success(message=None, status=200, **payload):
    body = dict(payload)
    if message is not None:
        body.setdefault('mensagem', message)
    return jsonify(body), status


def parse_json_body(required=False):
    data = request.get_json(silent=True)
    if data is None:
        if required:
            return None, json_error('Payload JSON obrigatório.', 400)
        return {}, None
    if not isinstance(data, dict):
        return None, json_error('Payload JSON inválido.', 400)
    return data, None


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if current_user.role != 'admin':
            return json_error('Negado', 403)
        return view_func(*args, **kwargs)

    return wrapped
```

Update `app/api/courses.py` to stop duplicating admin guards and `request.json` access:

```python
from flask import Blueprint, jsonify
from flask_login import login_required
from app.api.helpers import admin_required, json_error, parse_json_body
from app.services.course_service import CourseService

bp = Blueprint('courses_api', __name__, url_prefix='/api/courses')
course_service = CourseService()


@bp.route('/', methods=['POST'])
@login_required
@admin_required
def create_course():
    data, error_response = parse_json_body(required=True)
    if error_response:
        return error_response

    course, msg = course_service.create_course(data)
    if course:
        return jsonify({'id': course.id, 'nome': course.nome, 'mensagem': msg})
    return json_error(msg, 400)
```

Update the JSON-consuming admin endpoints in `app/api/admin.py` to the same pattern:

```python
from app.api.helpers import admin_required, json_error, parse_json_body


@bp.route('/atualizar_permissoes', methods=['POST'])
@login_required
@admin_required
def atualizar_permissoes():
    data, error_response = parse_json_body(required=True)
    if error_response:
        return error_response

    success, msg = admin_service.update_user_permissions(
        data.get('username'),
        data.get('can_create_events'),
    )
    if success:
        return jsonify({'mensagem': msg})
    return json_error(msg, 400)


@bp.route('/permissoes_curso_lote', methods=['POST'])
@login_required
@admin_required
def permissoes_curso_lote():
    data, error_response = parse_json_body(required=True)
    if error_response:
        return error_response

    count, msg = admin_service.bulk_update_permissions_by_course(
        data.get('course_id'),
        data.get('can_create_events'),
    )
    return jsonify({'mensagem': msg, 'count': count})
```

- [ ] **Step 4: Re-run the narrow tests and one non-admin guard regression**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_create_course_without_json_returns_structured_400 tests/test_api.py::test_admin_update_permissions_without_json_returns_structured_400 tests/test_api.py::test_importar_alunos_xlsx_requires_admin -q
```

Expected: PASS. The two new tests return JSON `400`, and the existing admin denial test still returns `403` with the same JSON contract.

- [ ] **Step 5: Commit the helper extraction slice**

Run:

```powershell
git add app/api/helpers.py app/api/courses.py app/api/admin.py tests/test_api.py
git commit -m "refactor: share api auth and json helpers"
```

---

### Task 2: Consolidate Async Import Endpoints In Admin API

**Files:**
- Modify: `app/api/admin.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing async XLSX regression test**

Append to `tests/test_api.py`:

```python
def test_importar_alunos_xlsx_start_and_status_processes_file(client, app, admin_user, monkeypatch):
    with app.app_context():
        db.session.add(Course(nome='Direito Async'))
        db.session.commit()

    class ImmediateThread:
        def __init__(self, target=None, args=None, daemon=None):
            self.target = target
            self.args = args or ()

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(admin_api, 'Thread', ImmediateThread)

    _login_admin(client)
    xlsx = _build_students_xlsx_for_api([
        ['Aluno Async', 'Uni', 'Direito Async', 'T1', '12345678901', '', '', '', '', '', 'RA-ASYNC-01', '', '', '', '', '', '', '', 1, 'async@example.com']
    ])

    start_res = client.post(
        '/api/importar_alunos_xlsx/start',
        data={'file': (xlsx, 'alunos_async.xlsx')},
        content_type='multipart/form-data',
    )

    assert start_res.status_code == 200
    start_payload = start_res.get_json()
    assert start_payload['job_id']
    assert start_payload['import_type'] == 'xlsx'

    status_res = client.get(
        f"/api/importar_alunos_xlsx/status/{start_payload['job_id']}?page=1&per_page=10"
    )

    assert status_res.status_code == 200
    payload = status_res.get_json()
    assert payload['completed'] is True
    assert payload['status'] == 'completed'
    assert payload['import_type'] == 'xlsx'
    assert payload['created'] == 1
    assert payload['updated'] == 0
    assert payload['errors_count'] == 0
    assert payload['pagination']['total_items'] == 1
    assert payload['rows'][0]['status'] == 'created'
```

- [ ] **Step 2: Run the new XLSX async test and confirm the current shape before refactoring**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_importar_alunos_xlsx_start_and_status_processes_file tests/test_api.py::test_importar_usuarios_csv_start_and_status_update_existing_user -q
```

Expected: The new test either fails because the XLSX async path diverges from the CSV contract, or passes and becomes the characterization guard for the refactor. Do not skip the refactor if it passes; this test is locking the contract.

- [ ] **Step 3: Extract the duplicated upload/job lifecycle helpers in `app/api/admin.py`**

Add these helpers near the existing import-job functions in `app/api/admin.py`:

```python
def _uploaded_file_or_error(field_name='file'):
    if field_name not in request.files:
        return None, (jsonify({'erro': 'Nenhum arquivo enviado'}), 400)

    uploaded_file = request.files[field_name]
    if not uploaded_file or uploaded_file.filename == '':
        return None, (jsonify({'erro': 'Nenhum arquivo selecionado'}), 400)

    return uploaded_file, None


def _new_import_job(import_type, created_by):
    return {
        'job_id': uuid4().hex,
        'import_type': import_type,
        'status': 'queued',
        'completed': False,
        'message': 'Importação iniciada.',
        'created_by': created_by,
        'updated_at': time.time(),
        'total_rows': 0,
        'processed_rows': 0,
        'created': 0,
        'updated': 0,
        'unchanged': 0,
        'errors_count': 0,
        'ignored_columns': [],
        'rows': [],
    }


def _start_async_import(import_type, worker_target):
    uploaded_file, error_response = _uploaded_file_or_error()
    if error_response:
        return error_response

    with _IMPORT_JOBS_LOCK:
        active_job = _get_active_job_for_user(current_user.username)
        if active_job:
            return jsonify({
                'job_id': active_job['job_id'],
                'import_type': active_job.get('import_type'),
                'message': 'Já existe uma importação em andamento para este usuário.',
                'reused': True,
            }), 202

        job = _new_import_job(import_type, current_user.username)
        _IMPORT_JOBS[job['job_id']] = job
        _persist_job(job)

    app_obj = current_app._get_current_object()
    file_content = uploaded_file.read()
    Thread(target=worker_target, args=(job['job_id'], file_content, app_obj), daemon=True).start()
    return jsonify({'job_id': job['job_id'], 'import_type': import_type, 'message': 'Importação em processamento.'})


def _import_status_response(job_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    filter_field = request.args.get('field', 'all', type=str)
    filter_query = request.args.get('q', '', type=str)
    payload = _build_import_job_payload(job_id, page, per_page, filter_field, filter_query)
    if not payload:
        return jsonify({'erro': 'Job não encontrado.'}), 404
    return jsonify(payload)
```

Then reduce the route bodies to one-liners:

```python
@bp.route('/importar_alunos_xlsx/start', methods=['POST'])
@login_required
@admin_required
def importar_alunos_xlsx_start():
    return _start_async_import('xlsx', _run_xlsx_import_job)


@bp.route('/importar_usuarios_csv/start', methods=['POST'])
@login_required
@admin_required
def importar_usuarios_csv_start():
    return _start_async_import('csv', _run_users_csv_import_job)


@bp.route('/importar_alunos_xlsx/status/<job_id>', methods=['GET'])
@login_required
@admin_required
def importar_alunos_xlsx_status(job_id):
    return _import_status_response(job_id)


@bp.route('/importar_usuarios_csv/status/<job_id>', methods=['GET'])
@login_required
@admin_required
def importar_usuarios_csv_status(job_id):
    return _import_status_response(job_id)
```

- [ ] **Step 4: Run the focused import test slice**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_importar_usuarios_csv_start_and_status_update_existing_user tests/test_api.py::test_importar_alunos_xlsx_start_and_status_processes_file tests/test_api.py::test_importar_alunos_xlsx_admin_processes_file -q
```

Expected: PASS for sync and async import flows.

- [ ] **Step 5: Commit the admin import refactor**

Run:

```powershell
git add app/api/admin.py tests/test_api.py
git commit -m "refactor: unify admin import handlers"
```

---

### Task 3: Extract AVA/Moodle Payload And Validation Helpers

**Files:**
- Modify: `app/api/auth.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing tests for the new AVA helpers and route contracts**

If missing, add this import near the top of `tests/test_api.py`:

```python
from app.api import auth as auth_api
```

Append to `tests/test_api.py`:

```python
def test_extract_moodle_identity_reads_cpf_name_and_email(app):
    payload = {
        'username': '123.456.789-01',
        'lis_person_name_given': 'Maria',
        'lis_person_name_family': 'Silva',
        'lis_person_contact_email_primary': 'Maria.Silva@unieuro.edu.br',
    }

    with app.app_context():
        identity = auth_api._extract_moodle_identity(payload)

    assert identity == {
        'cpf': '12345678901',
        'nome': 'Maria Silva',
        'email': 'maria.silva@unieuro.edu.br',
    }


def test_ava_direct_rejects_email_outside_allowed_domain(client, app):
    app.config.update(
        MOODLE_LOGIN_ENABLED=True,
        MOODLE_ALLOWED_EMAIL_DOMAIN='unieuro.edu.br',
    )

    res = client.post('/api/ava/direct', json={
        'username': '12345678901',
        'email': 'externo@test.local',
        'name': 'Pessoa Externa',
    })

    assert res.status_code == 403
    assert res.get_json()['message'] == 'Acesso restrito à comunidade acadêmica Unieuro.'
```

- [ ] **Step 2: Run the new AVA tests and verify at least the helper test fails before extraction**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_extract_moodle_identity_reads_cpf_name_and_email tests/test_api.py::test_ava_direct_rejects_email_outside_allowed_domain -q
```

Expected: FAIL on `AttributeError: module 'app.api.auth' has no attribute '_extract_moodle_identity'`.

- [ ] **Step 3: Extract reusable private helpers in `app/api/auth.py`**

Add these helpers near the top of `app/api/auth.py`:

```python
def _moodle_payload():
    return request.form or request.get_json(silent=True) or {}


def _moodle_login_disabled_response():
    return jsonify({'status': 'error', 'message': 'Login AVA desativado.'}), 404


def _extract_moodle_identity(payload):
    cpf_field = (current_app.config.get('MOODLE_CPF_FIELD') or 'custom_cpf').strip()
    cpf_raw = (
        payload.get(cpf_field)
        or payload.get('username')
        or payload.get('ext_user_username')
        or payload.get('custom_cpf')
        or payload.get('cpf')
        or payload.get('lis_person_sourcedid')
        or payload.get('user_id')
    )
    nome = (
        payload.get('lis_person_name_full')
        or payload.get('name')
        or f"{payload.get('lis_person_name_given', '').strip()} {payload.get('lis_person_name_family', '').strip()}".strip()
    )
    email = (payload.get('lis_person_contact_email_primary') or payload.get('email') or '').strip().lower()
    return {
        'cpf': normalize_cpf(cpf_raw),
        'nome': nome,
        'email': email,
    }


def _validate_moodle_consumer(payload):
    expected_consumer_key = (current_app.config.get('MOODLE_TOOL_CONSUMER_KEY') or '').strip()
    received_consumer_key = (
        payload.get('oauth_consumer_key')
        or payload.get('custom_oauth_consumer_key')
        or ''
    ).strip()

    if expected_consumer_key:
        if not received_consumer_key:
            return jsonify({'status': 'error', 'message': 'oauth_consumer_key ausente no launch LTI.'}), 403
        if received_consumer_key != expected_consumer_key:
            return jsonify({'status': 'error', 'message': 'Consumer key da ferramenta externa inválido.'}), 403

    shared_secret = (current_app.config.get('MOODLE_TOOL_SHARED_SECRET') or '').strip()
    if shared_secret and not expected_consumer_key:
        received_secret = (
            payload.get('custom_ava_secret')
            or payload.get('ava_secret')
            or received_consumer_key
            or ''
        ).strip()
        if not received_secret:
            return jsonify({'status': 'error', 'message': 'Credencial da ferramenta externa ausente no launch (custom_ava_secret/oauth_consumer_key).'}), 403
        if received_secret != shared_secret:
            return jsonify({'status': 'error', 'message': 'Assinatura da ferramenta externa inválida.'}), 403

    return None


def _validate_moodle_allowed_domain(email):
    allowed_domain = (current_app.config.get('MOODLE_ALLOWED_EMAIL_DOMAIN') or '').strip().lower()
    if allowed_domain and (not email or not email.endswith(f'@{allowed_domain}')):
        return jsonify({'status': 'error', 'message': 'Acesso restrito à comunidade acadêmica Unieuro.'}), 403
    return None


def _authenticate_moodle_identity(identity):
    user = auth_service.authenticate_or_provision_from_moodle(
        cpf=identity['cpf'],
        nome=identity['nome'],
        email=identity['email'],
    )
    if not user:
        return None, jsonify({'status': 'error', 'message': 'Não foi possível autenticar via AVA.'}), 401
    return user, None
```

Then collapse the duplicated route bodies:

```python
@bp.route('/ava/launch', methods=['GET', 'POST'])
def ava_launch_login():
    if not current_app.config.get('MOODLE_LOGIN_ENABLED'):
        return _moodle_login_disabled_response()

    if request.method == 'GET':
        ...

    payload = _moodle_payload()
    identity = _extract_moodle_identity(payload)
    if not identity['cpf']:
        return jsonify({'status': 'error', 'message': 'CPF não recebido do AVA.'}), 400

    consumer_error = _validate_moodle_consumer(payload)
    if consumer_error:
        return consumer_error

    user, auth_error = _authenticate_moodle_identity(identity)
    if auth_error:
        return auth_error

    _start_authenticated_session(user)
    return redirect(url_for('main.index'))


@bp.route('/ava/direct', methods=['POST'])
def ava_direct_login():
    if not current_app.config.get('MOODLE_LOGIN_ENABLED'):
        return _moodle_login_disabled_response()

    payload = _moodle_payload()
    identity = _extract_moodle_identity(payload)
    if not identity['cpf']:
        return jsonify({'status': 'error', 'message': 'CPF não recebido.'}), 400

    domain_error = _validate_moodle_allowed_domain(identity['email'])
    if domain_error:
        return domain_error

    user, auth_error = _authenticate_moodle_identity(identity)
    if auth_error:
        return auth_error

    _start_authenticated_session(user)
    return redirect(url_for('main.index'))
```

- [ ] **Step 4: Run the focused auth route tests**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_extract_moodle_identity_reads_cpf_name_and_email tests/test_api.py::test_ava_direct_rejects_email_outside_allowed_domain tests/test_api.py::test_password_forgot_always_returns_success tests/test_api.py::test_password_reset_with_token_updates_password -q
```

Expected: PASS.

- [ ] **Step 5: Commit the AVA extraction**

Run:

```powershell
git add app/api/auth.py tests/test_api.py
git commit -m "refactor: extract ava payload helpers"
```

---

### Task 4: Centralize Notification Links And Event Email Context

**Files:**
- Modify: `app/services/admin_service.py`
- Modify: `app/services/auth_service.py`
- Modify: `app/services/event_service.py`
- Test: `tests/test_services.py`
- Test: `tests/test_event_responsibles.py`

- [ ] **Step 1: Write failing tests for URLs that must respect BASE_PATH**

If missing, add this import near the top of `tests/test_services.py`:

```python
from flask import current_app
```

Append to `tests/test_services.py`:

```python
def test_admin_service_manual_enroll_uses_base_path_in_urls(app, admin_user):
    with app.app_context():
        current_app.config['BASE_URL'] = 'https://portal.unieuro.br'
        current_app.config['BASE_PATH'] = '/unieventos'

        participant = User(
            username='manual_base_path_user',
            role='participante',
            nome='Participante Base Path',
            cpf='11122233366',
            email='manual_base_path@test.local',
        )
        participant.set_password('1234')
        db.session.add(participant)
        db.session.flush()

        event = Event(
            owner_username='admin_test',
            nome='Evento Base Path',
            descricao='Descricao',
            tipo='PADRAO',
            token_publico='token-base-path',
            data_inicio=date(2030, 4, 10),
            hora_inicio=time(18, 0),
        )
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            nome='Atividade Base Path',
            local='Laboratorio',
            descricao='Descricao atividade',
            data_atv=date(2030, 4, 11),
            hora_atv=time(19, 30),
            carga_horaria=4,
            vagas=25,
        )
        db.session.add(activity)
        db.session.commit()

        sent_payloads = []
        service = AdminService()
        service.notification_service.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

        success, msg = service.manual_enroll(participant.cpf, activity.id)

        assert success is True
        assert msg == 'Inscrição realizada com sucesso.'
        assert sent_payloads[0]['template_data']['event_details_url'] == 'https://portal.unieuro.br/unieventos/inscrever/token-base-path'
        assert sent_payloads[0]['template_data']['my_events_url'] == 'https://portal.unieuro.br/unieventos/meus_eventos'


def test_auth_service_request_password_reset_uses_base_path_in_reset_url(app):
    with app.app_context():
        current_app.config['BASE_URL'] = 'https://portal.unieuro.br'
        current_app.config['BASE_PATH'] = '/unieventos'

        user = User(
            username='reset_base_path_user',
            role='participante',
            nome='Reset Base Path',
            cpf='44455566677',
            email='reset_base_path@test.local',
        )
        user.set_password('1234')
        db.session.add(user)
        db.session.commit()

        sent_payloads = []
        service = AuthService()
        service.notifier.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

        result = service.request_password_reset('reset_base_path@test.local')

        assert result is True
        assert sent_payloads[0]['template_data']['reset_url'].startswith(
            'https://portal.unieuro.br/unieventos/resetar-senha/'
        )
```

If missing, add this import near the top of `tests/test_event_responsibles.py`:

```python
from flask import current_app
```

Append to `tests/test_event_responsibles.py`:

```python
def test_event_service_create_notification_uses_base_path_links(app):
    with app.app_context():
        current_app.config['BASE_URL'] = 'https://portal.unieuro.br'
        current_app.config['BASE_PATH'] = '/unieventos'

        owner = _persist_user(
            'notify_base_path_owner',
            role='professor',
            cpf='90000000043',
            can_create_events=True,
            email='notify_base_path_owner@test.local',
        )
        service = EventService()
        sent_payloads = []
        service.notification_service.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

        service.create_event(owner.username, _event_payload(nome='Evento Base Path Notificacao'))

        assert len(sent_payloads) == 1
        template_data = sent_payloads[0]['template_data']
        assert template_data['event_link'].startswith('https://portal.unieuro.br/unieventos/inscrever/')
        assert template_data['manage_link'] == 'https://portal.unieuro.br/unieventos/eventos_admin'
```

- [ ] **Step 2: Run the focused service tests and verify they fail before the refactor**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_services.py::test_admin_service_manual_enroll_uses_base_path_in_urls tests/test_services.py::test_auth_service_request_password_reset_uses_base_path_in_reset_url tests/test_event_responsibles.py::test_event_service_create_notification_uses_base_path_links -q
```

Expected: FAIL because current services build URLs manually from `BASE_URL` and ignore `BASE_PATH`.

- [ ] **Step 3: Replace ad-hoc URL building with shared helpers and extract owner notification sender**

In `app/services/admin_service.py`, import and use `build_absolute_app_url`:

```python
from app.utils import build_absolute_app_url


def _notify_manual_enrollment(self, user, activity):
    if not user or not user.email or not activity:
        return

    event = activity.event
    event_path = f"/inscrever/{event.token_publico}" if event and event.token_publico else '/meus_eventos'
    event_details_url = build_absolute_app_url(event_path)
    my_events_url = build_absolute_app_url('/meus_eventos')
    ...
```

In `app/services/auth_service.py`, replace manual `BASE_URL` concatenation with a private helper:

```python
from app.utils import build_absolute_app_url


def _account_email_context(self):
    return {
        'year': datetime.now().year,
        'app_url': build_absolute_app_url('/'),
        'unsubscribe_url': build_absolute_app_url('/unsubscribe/'),
    }


def request_password_reset(self, email):
    ...
    reset_url = build_absolute_app_url(f'/resetar-senha/{token}')
    return self.notifier.send_email_task(
        to_email=user.email,
        subject='Recuperacao de senha - EuroEventos',
        template_name='password_reset.html',
        template_data={
            'user_name': user.nome,
            'reset_url': reset_url,
            'expires_minutes': int(self._password_reset_max_age() / 60),
            'year': datetime.now().year,
        },
    )
```

In `app/services/event_service.py`, introduce one sender for owner notifications:

```python
from app.utils import build_absolute_app_url


def _send_owner_event_notification(self, owners, subject, template_name, template_data):
    for owner in owners:
        if not owner or not owner.email:
            continue
        self.notification_service.send_email_task(
            to_email=owner.email,
            subject=subject,
            template_name=template_name,
            template_data={
                'user_name': owner.nome or owner.username,
                **template_data,
            },
        )


def _event_schedule_labels(self, date_value, time_value):
    event_date = date_value.strftime('%d/%m/%Y') if date_value else '-'
    event_time = time_value.strftime('%H:%M') if time_value else '-'
    return event_date, event_time


def _notify_owner_event_created(self, event):
    event_date, event_time = self._event_schedule_labels(event.data_inicio, event.hora_inicio)
    self._send_owner_event_notification(
        self._get_event_responsible_users(event),
        subject=f'Evento criado: {event.nome}',
        template_name='event_created_owner.html',
        template_data={
            'event_name': event.nome,
            'event_type': event.tipo,
            'event_date': event_date,
            'event_time': event_time,
            'event_status': event.status,
            'event_link': build_absolute_app_url(f'/inscrever/{event.token_publico}'),
            'manage_link': build_absolute_app_url('/eventos_admin'),
            'year': datetime.now().year,
        },
    )
```

Apply the same sender to update/delete and to participant-facing enrollment/presence emails where links are currently assembled manually.

- [ ] **Step 4: Run the narrow notification suite and one existing regression**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_services.py::test_admin_service_manual_enroll_uses_base_path_in_urls tests/test_services.py::test_auth_service_request_password_reset_uses_base_path_in_reset_url tests/test_event_responsibles.py::test_event_service_create_notification_uses_base_path_links tests/test_services.py::test_event_service_delete_event_sends_email_to_owner -q
```

Expected: PASS.

- [ ] **Step 5: Commit the notification refactor**

Run:

```powershell
git add app/services/admin_service.py app/services/auth_service.py app/services/event_service.py tests/test_services.py tests/test_event_responsibles.py
git commit -m "refactor: centralize notification links and contexts"
```

---

### Task 5: Reduce Test Duplication For Authentication And Role Matrices

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the parametrized replacement tests before deleting duplicated sequences**

Append to `tests/test_api.py`:

```python
@pytest.mark.parametrize(
    ('username_key', 'expected_links'),
    [
        ('gestor_username', {'/cursos', '/usuarios', '/analitico', '/eventos_admin'}),
        ('coord_username', {'/analitico', '/eventos_admin'}),
        ('participant_username', set()),
    ],
)
def test_authenticated_navbar_links_by_role_matrix(client, app, admin_user, auth_session, username_key, expected_links):
    seeded = _seed_dashboard_analytics_data(app)

    auth_session.login(seeded[username_key])
    nav_html = _extract_main_nav(client.get('/').get_data(as_text=True))

    for href in ['/cursos', '/usuarios', '/analitico', '/eventos_admin']:
        assert (f'href="{href}"' in nav_html) is (href in expected_links)


@pytest.mark.parametrize(
    ('username_key', 'expected_status'),
    [
        ('gestor_username', 200),
        ('coord_username', 200),
        ('prof_eng_a_username', 403),
        ('participant_username', 403),
    ],
)
def test_analytics_page_visibility_matrix(client, app, admin_user, auth_session, username_key, expected_status):
    seeded = _seed_dashboard_analytics_data(app)

    auth_session.login(seeded[username_key])
    res = client.get('/analitico')

    assert res.status_code == expected_status
```

- [ ] **Step 2: Run the new parametrized matrix tests and compare them to the old coverage**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_authenticated_navbar_links_by_role_matrix tests/test_api.py::test_analytics_page_visibility_matrix -q
```

Expected: PASS. These tests are characterizing existing behavior before the old repeated sequences are deleted.

- [ ] **Step 3: Add the auth fixture and replace repeated login/logout sequences**

In `tests/conftest.py`, add this fixture:

```python
@pytest.fixture
def auth_session(client):
    class AuthSession:
        def login(self, username, password='1234'):
            client.get('/api/logout')
            return client.post('/api/login', json={'username': username, 'password': password})

        def logout(self):
            return client.get('/api/logout')

        def switch(self, username, password='1234'):
            self.logout()
            return client.post('/api/login', json={'username': username, 'password': password})

    return AuthSession()
```

Then replace the long imperative sequences in `tests/test_api.py` with the parametrized tests and a small helper for repeated href assertions:

```python
def _assert_nav_links(nav_html, expected_links):
    for href in ['/cursos', '/usuarios', '/analitico', '/eventos_admin']:
        assert (f'href="{href}"' in nav_html) is (href in expected_links)
```

Update the existing navbar and analytics tests to call `auth_session.switch(...)` instead of repeating `client.get('/api/logout')` and `_login_user(...)` blocks.

- [ ] **Step 4: Run the focused API role suite after removing the duplicated blocks**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_authenticated_navbar_links_by_role_matrix tests/test_api.py::test_analytics_page_visibility_matrix tests/test_api.py::test_dashboard_page_no_longer_renders_management_analytics -q
```

Expected: PASS.

- [ ] **Step 5: Commit the test cleanup**

Run:

```powershell
git add tests/conftest.py tests/test_api.py
git commit -m "test: reduce duplicated auth setup in api coverage"
```

---

## Validation Sequence

Run these commands after each task instead of waiting for the end:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_api.py -q
```

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_services.py tests/test_event_responsibles.py -q
```

At the end of the whole plan, run the full regression slice touched by this refactor:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_services.py tests/test_event_responsibles.py -q
```

Expected: PASS with no route contract regressions.

## Rollout Notes

- Execute Task 1 before the others so the admin/courses modules stop depending on raw `request.json` and duplicated `403` branches.
- Execute Task 2 before broadening admin cleanup; the async import routes are the biggest localized duplication hotspot.
- Execute Task 3 before touching AVA behavior in templates or docs.
- Execute Task 4 after Task 3 so auth notifications and event notifications converge on the same URL-building approach.
- Execute Task 5 last; it changes only tests and should land after the functional refactors stabilize.
