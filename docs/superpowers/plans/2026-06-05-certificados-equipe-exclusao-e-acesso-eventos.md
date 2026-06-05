# Certificados de Equipe - Exclusao e Acesso na Pagina de Eventos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bloquear a exclusao de eventos com destinatarios de certificados de equipe vinculados e adicionar um acesso visual separado para certificados de equipe nas superficies de eventos que ja exibem a acao de certificados de participantes.

**Architecture:** A protecao de exclusao continua centralizada em `EventService.get_event_delete_block_status()` e se propaga para serializacao e resposta da API de exclusao. O novo acesso de equipe reutiliza a permissao ja existente de visualizacao de certificados e aponta para `/certificados_equipe/<event_id>`, mantendo o fluxo de participantes intacto e separado.

**Tech Stack:** Flask, SQLAlchemy, Jinja, JavaScript inline em templates, pytest.

---

**Commit Policy:** O usuario aprovou commits para este follow-up. Mantenha commits pequenos e tematicos.

## File Structure

- Modify `app/services/event_service.py`: incluir `EventTeamCertificateRecipient` no status de bloqueio de exclusao e na mensagem de erro.
- Modify `app/serializers.py`: expor a nova contagem de destinatarios de equipe no payload serializado de evento.
- Modify `app/api/events.py`: devolver a nova contagem ao bloquear a exclusao pela API.
- Modify `app/templates/base.html`: permitir `pathUrl('/certificados_equipe/...')` quando a acao for gerada em templates JS.
- Modify `app/templates/events_admin.html`: adicionar botao/icone separado para certificados de equipe na listagem de eventos administrativos.
- Modify `app/templates/dashboard.html`: adicionar acao separada para certificados de equipe no card/lista de eventos do dashboard que hoje ja mostra o icone de certificados.
- Modify `tests/test_services.py`: cobrir o novo bloqueio de exclusao por destinatarios de equipe.
- Modify `tests/test_api.py`: cobrir a resposta da API de exclusao e a presenca do novo atalho separado nas paginas de eventos.
- No source changes for cleanup: remover o evento temporario `Evento Verificacao Designer Certificados` com comando pontual apos a validacao.

## Task 1: Bloquear Exclusao De Evento Com Destinatarios De Equipe

**Files:**
- Modify: `app/services/event_service.py`
- Modify: `app/serializers.py`
- Modify: `app/api/events.py`
- Test: `tests/test_services.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing service test**

Adicionar em `tests/test_services.py`, logo apos `test_event_service_delete_event_blocks_when_event_has_legacy_enrollment`:

```python
def test_event_service_delete_event_blocks_when_event_has_team_certificate_recipients(app):
    from app.models import EventTeamCertificateRecipient

    with app.app_context():
        owner = User(
            username='event_owner_blocked_team_cert',
            role='professor',
            nome='Owner Blocked Team Cert',
            cpf='55566677793',
            email='owner_blocked_team_cert@test.local',
            can_create_events=True,
        )
        owner.set_password('1234')
        db.session.add(owner)
        db.session.commit()

        service = EventService()
        sent_payloads = []
        service.notification_service.send_email_task = lambda **kwargs: sent_payloads.append(kwargs) or True

        event = service.create_event(owner.username, {
            'nome': 'Evento Com Destinatario de Equipe',
            'descricao': 'Desc',
            'is_rapido': True,
            'carga_horaria_rapida': 2,
            'data_inicio': '2030-01-06',
            'hora_inicio': '12:00',
        })
        sent_payloads.clear()

        recipient = EventTeamCertificateRecipient(
            event_id=event.id,
            nome='Equipe Teste',
            email='team_delete_block@test.local',
            role_label='Equipe organizadora',
            source='manual',
        )
        db.session.add(recipient)
        db.session.commit()

        status = service.get_event_delete_block_status(event)
        success, msg = service.delete_event(event.id, owner)

        assert status['linked_event_registrations_count'] == 0
        assert status['linked_enrollments_count'] == 0
        assert status['linked_team_certificate_recipients_count'] == 1
        assert status['has_linked_records'] is True
        assert success is False
        assert msg == 'Não é possível excluir o evento porque existem inscrições, matrículas ou destinatários de certificados de equipe vinculados.'
        assert len(sent_payloads) == 0
        assert db.session.get(Event, event.id) is not None
```

- [ ] **Step 2: Run the service test to verify it fails**

Run: `python -m pytest tests/test_services.py::test_event_service_delete_event_blocks_when_event_has_team_certificate_recipients -q`

Expected: FAIL because `linked_team_certificate_recipients_count` does not exist yet and/or the message still mentions only inscricoes e matriculas.

- [ ] **Step 3: Write the failing API test**

Adicionar em `tests/test_api.py`, perto dos testes de exclusao/bloqueio de evento:

```python
def test_delete_event_endpoint_reports_team_certificate_recipient_block(client, app, admin_user):
    with app.app_context():
        owner = User(
            username='event_delete_team_owner',
            role='professor',
            nome='Owner Delete Team',
            cpf='55566677794',
            email='event_delete_team_owner@test.local',
            can_create_events=True,
        )
        owner.set_password('1234')
        db.session.add(owner)
        db.session.commit()

        service = EventService()
        event = service.create_event(owner.username, {
            'nome': 'Evento API Block Team Recipient',
            'descricao': 'Desc',
            'is_rapido': True,
            'carga_horaria_rapida': 2,
            'data_inicio': '2030-01-07',
            'hora_inicio': '12:00',
        })

        recipient = EventTeamCertificateRecipient(
            event_id=event.id,
            nome='Equipe API',
            email='event_delete_team_api@test.local',
            role_label='Equipe organizadora',
            source='manual',
        )
        db.session.add(recipient)
        db.session.commit()
        event_id = event.id

    _login_user(client, 'event_delete_team_owner')
    res = client.delete(f'/api/deletar_evento/{event_id}')

    assert res.status_code == 400
    payload = res.get_json()
    assert payload['linked_event_registrations_count'] == 0
    assert payload['linked_enrollments_count'] == 0
    assert payload['linked_team_certificate_recipients_count'] == 1
    assert 'certificados de equipe' in payload['erro'].lower()
```

- [ ] **Step 4: Run the API test to verify it fails**

Run: `python -m pytest tests/test_api.py::test_delete_event_endpoint_reports_team_certificate_recipient_block -q`

Expected: FAIL because the API response does not expose `linked_team_certificate_recipients_count` yet.

- [ ] **Step 5: Implement the minimal exclusion-block changes**

Em `app/services/event_service.py`, importar `EventTeamCertificateRecipient` junto dos outros modelos usados no metodo e alterar `get_event_delete_block_status()` para este formato:

```python
    @staticmethod
    def get_event_delete_block_status(event):
        if not event:
            return {
                'linked_event_registrations_count': 0,
                'linked_enrollments_count': 0,
                'linked_team_certificate_recipients_count': 0,
                'has_linked_records': False,
                'delete_block_reason': None,
            }

        linked_event_registrations_count = EventRegistration.query.filter_by(
            event_id=event.id
        ).count()
        linked_enrollments_count = (
            Enrollment.query
            .join(Activity, Enrollment.activity_id == Activity.id)
            .filter(Activity.event_id == event.id)
            .count()
        )
        linked_team_certificate_recipients_count = EventTeamCertificateRecipient.query.filter_by(
            event_id=event.id
        ).count()
        has_linked_records = (
            linked_event_registrations_count > 0
            or linked_enrollments_count > 0
            or linked_team_certificate_recipients_count > 0
        )

        return {
            'linked_event_registrations_count': linked_event_registrations_count,
            'linked_enrollments_count': linked_enrollments_count,
            'linked_team_certificate_recipients_count': linked_team_certificate_recipients_count,
            'has_linked_records': has_linked_records,
            'delete_block_reason': (
                'Não é possível excluir o evento porque existem inscrições, matrículas ou destinatários de certificados de equipe vinculados.'
                if has_linked_records else None
            ),
        }
```

Em `app/serializers.py`, expandir o default e o payload retornado:

```python
    delete_block_status = {
        'linked_event_registrations_count': 0,
        'linked_enrollments_count': 0,
        'linked_team_certificate_recipients_count': 0,
        'has_linked_records': False,
        'delete_block_reason': None,
    }
```

e mais abaixo:

```python
        'linked_team_certificate_recipients_count': delete_block_status['linked_team_certificate_recipients_count'],
```

Em `app/api/events.py`, incluir a nova contagem na resposta `400`:

```python
        return jsonify({
            "erro": msg,
            "linked_event_registrations_count": delete_block_status['linked_event_registrations_count'],
            "linked_enrollments_count": delete_block_status['linked_enrollments_count'],
            "linked_team_certificate_recipients_count": delete_block_status['linked_team_certificate_recipients_count'],
        }), 400
```

- [ ] **Step 6: Run both focused tests to verify they pass**

Run: `python -m pytest tests/test_services.py::test_event_service_delete_event_blocks_when_event_has_team_certificate_recipients tests/test_api.py::test_delete_event_endpoint_reports_team_certificate_recipient_block -q`

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add app/services/event_service.py app/serializers.py app/api/events.py tests/test_services.py tests/test_api.py
git commit -m "fix(events): block deletion when team certificates exist"
```

Expected: commit created successfully.

## Task 2: Adicionar Acao Separada De Certificados De Equipe Nas Paginas De Eventos

**Files:**
- Modify: `app/templates/base.html`
- Modify: `app/templates/events_admin.html`
- Modify: `app/templates/dashboard.html`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing UI coverage test**

Adicionar em `tests/test_api.py`, perto dos testes de visualizacao de certificados no gerenciamento de eventos:

```python
def test_event_pages_expose_separate_team_certificate_access(client, app, admin_user):
    seeded = _seed_certificate_management_data(app)

    _login_user(client, seeded['owner_username'])

    events_admin_res = client.get('/eventos_admin')
    dashboard_res = client.get('/')

    assert events_admin_res.status_code == 200
    events_admin_html = events_admin_res.get_data(as_text=True)
    assert '/designer_certificado/${ev.id}' in events_admin_html
    assert '/certificados_equipe/${ev.id}' in events_admin_html
    assert 'Certificados da Equipe' in events_admin_html

    assert dashboard_res.status_code == 200
    dashboard_html = dashboard_res.get_data(as_text=True)
    assert '/designer_certificado/${ev.id}' in dashboard_html
    assert '/certificados_equipe/${ev.id}' in dashboard_html
```

- [ ] **Step 2: Run the UI test to verify it fails**

Run: `python -m pytest tests/test_api.py::test_event_pages_expose_separate_team_certificate_access -q`

Expected: FAIL because the event pages only expose the participant certificate action today.

- [ ] **Step 3: Implement the minimal UI changes**

Em `app/templates/base.html`, expandir `pathUrl()` para aceitar a nova rota:

```html
                url.startsWith('/designer_certificado') ||
                url.startsWith('/designer_certificado_institucional') ||
                url.startsWith('/gerenciar_entregas') ||
                url.startsWith('/certificados_equipe') ||
```

Em `app/templates/events_admin.html`, manter o botao atual de participante e adicionar um segundo botao separado para equipe, usando o mesmo gate de permissao:

```html
                            ${ev.can_view_certificates ? `
                            <a href="${pathUrl(`/designer_certificado/${ev.id}`)}" class="btn btn-sm btn-light border d-flex align-items-center justify-content-center" title="Certificados de Participantes">
                                <i class="fa-solid fa-certificate text-warning"></i>
                            </a>
                            <a href="${pathUrl(`/certificados_equipe/${ev.id}`)}" class="btn btn-sm btn-light border d-flex align-items-center justify-content-center" title="Certificados da Equipe">
                                <i class="fa-solid fa-users text-primary"></i>
                            </a>` : `
                            <button class="btn btn-sm btn-light border d-flex align-items-center justify-content-center" title="Certificado indisponível" disabled>
                                <i class="fa-solid fa-certificate text-muted"></i>
                            </button>
                            <button class="btn btn-sm btn-light border d-flex align-items-center justify-content-center" title="Certificados da equipe indisponíveis" disabled>
                                <i class="fa-solid fa-users text-muted"></i>
                            </button>`}
```

Em `app/templates/dashboard.html`, aplicar a mesma separacao no rodape do card de evento:

```html
                ${ev.can_view_certificates ? `
                <a href="${pathUrl(`/designer_certificado/${ev.id}`)}" class="btn btn-sm btn-light border" title="Certificados de Participantes">
                    <i class="fa-solid fa-certificate"></i>
                </a>
                <a href="${pathUrl(`/certificados_equipe/${ev.id}`)}" class="btn btn-sm btn-light border" title="Certificados da Equipe">
                    <i class="fa-solid fa-users"></i>
                </a>` : ''}
```

- [ ] **Step 4: Run the UI test to verify it passes**

Run: `python -m pytest tests/test_api.py::test_event_pages_expose_separate_team_certificate_access -q`

Expected: PASS.

- [ ] **Step 5: Run a focused regression subset for certificate/event management pages**

Run: `python -m pytest tests/test_api.py::test_event_management_allows_gestor_certificate_visualization_but_blocks_certificate_mutations tests/test_api.py::test_team_certificate_pages_load_for_owner_and_gestor tests/test_api.py::test_certificate_management_endpoints_allow_admin_owner_course_coordinator_extensao_and_gestor_view -q`

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add app/templates/base.html app/templates/events_admin.html app/templates/dashboard.html tests/test_api.py
git commit -m "feat(events): add team certificate access to event pages"
```

Expected: commit created successfully.

## Task 3: Remover O Evento Temporario E Rodar Verificacao Final

**Files:**
- No source files unless cleanup reveals an unexpected dependency.

- [ ] **Step 1: Remove temporary team recipients and the validation event**

Run:

```bash
python -c "from app import create_app; from app.extensions import db; from app.models import Event, EventTeamCertificateRecipient; app=create_app(); ctx=app.app_context(); ctx.push(); event = Event.query.filter_by(nome='Evento Verificacao Designer Certificados').first();
if not event:
    print('not-found')
else:
    EventTeamCertificateRecipient.query.filter_by(event_id=event.id).delete(synchronize_session=False)
    db.session.flush()
    db.session.delete(event)
    db.session.commit()
    print(f'removed:{event.id}')"
```

Expected: `removed:<id>` or `not-found` if cleanup already happened.

- [ ] **Step 2: Verify the temporary event is gone**

Run:

```bash
python -c "from app import create_app; from app.models import Event; app=create_app(); ctx=app.app_context(); ctx.push(); print(Event.query.filter_by(nome='Evento Verificacao Designer Certificados').count())"
```

Expected: `0`

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Run final diff hygiene check**

Run: `git diff --check`

Expected: no output.

- [ ] **Step 5: Check final workspace status**

Run: `git status --short`

Expected: clean workspace after the Task 1 and Task 2 commits, with no leftover source changes from the temporary-event cleanup.
