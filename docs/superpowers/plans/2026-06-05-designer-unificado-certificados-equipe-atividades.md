# Designer Unificado e Gestao de Certificados de Equipe por Atividade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unificar o bootstrap do designer de certificados de participantes e equipe, evitar tela em branco com fallback seguro e tornar a gestao/envio de certificados de equipe derivada por padrao de atividades vinculadas ao evento e responsaveis.

**Architecture:** O backend passara a normalizar e entregar um bootstrap comum para o designer, tirando do template HTML a responsabilidade de decidir o estado inicial do layout. Para equipe, a fonte de verdade deixa de ser uma lista parcialmente manual e passa a ser uma lista resolvida a partir de atividades, responsaveis e complementos manuais, reaproveitada por preview, listagem e envio.

**Tech Stack:** Flask, SQLAlchemy, Jinja, JavaScript inline em templates, pytest.

---

**Commit Policy:** O usuario aprovou commits nesta rodada. Mantenha commits pequenos e tematicos.

## File Structure

- Modify `app/services/certificate_service.py`: concentrar normalizacao, defaults e bootstrap comum do designer para `event` e `team_event`.
- Modify `app/services/event_team_certificate_service.py`: introduzir resolucao padrao de destinatarios de equipe por atividades + responsaveis + complementos manuais.
- Modify `app/api/certificates.py`: expor endpoint de bootstrap do designer, reaproveitar contrato comum e mudar a listagem/envio de equipe para a lista resolvida.
- Modify `app/main/routes.py`: simplificar as rotas do designer para renderizarem a casca da pagina e o modo correto, sem reconstruir payloads ad hoc.
- Modify `app/templates/certificate_designer.html`: consumir bootstrap comum via fetch, mostrar estado de erro/fallback e remover dependencia de estado inicial fragil embutido em Jinja.
- Modify `app/templates/team_certificate_delivery.html`: consumir lista resolvida, explicitar origem automatica e manter CRUD manual como complemento.
- Test `tests/test_api.py`: cobrir bootstrap do designer, fallback seguro, equipe resolvida e regressao do preview/envio.
- Test `tests/test_services.py`: cobrir resolver de destinatarios de equipe e normalizacao/fallback do template.

## Task 1: Criar O Contrato Comum De Bootstrap E Template

**Files:**
- Modify: `app/services/certificate_service.py`
- Test: `tests/test_services.py`

- [ ] **Step 1: Write the failing service test for participant bootstrap fallback**

Adicionar em `tests/test_services.py`, perto dos testes de `CertificateService`:

```python
def test_certificate_service_build_designer_bootstrap_falls_back_when_event_template_is_invalid(app):
    with app.app_context():
        event = Event(
            owner_username='admin_test',
            nome='Evento Bootstrap Invalido',
            descricao='Desc',
            tipo='PADRAO',
            data_inicio=date(2030, 1, 10),
            hora_inicio=time(10, 0),
            cert_template_json='{"broken": ',
            cert_bg_path='file/fundo_padrao.png',
        )
        db.session.add(event)
        db.session.commit()

        service = CertificateService()
        bootstrap = service.build_designer_bootstrap(event, designer_mode='event')

        assert bootstrap['designer_mode'] == 'event'
        assert bootstrap['entity_id'] == event.id
        assert bootstrap['template']['version'] == 2
        assert bootstrap['template']['elements']
        assert bootstrap['warnings']
        assert any('fallback' in warning['code'] for warning in bootstrap['warnings'])
```

- [ ] **Step 2: Run the service test to verify it fails**

Run: `python -m pytest tests/test_services.py::test_certificate_service_build_designer_bootstrap_falls_back_when_event_template_is_invalid -q`

Expected: FAIL because `build_designer_bootstrap` does not exist yet.

- [ ] **Step 3: Write the failing service test for team bootstrap**

Adicionar em `tests/test_services.py`, logo abaixo:

```python
def test_certificate_service_build_designer_bootstrap_supports_team_event_mode(app):
    with app.app_context():
        event = Event(
            owner_username='admin_test',
            nome='Evento Bootstrap Equipe',
            descricao='Desc',
            tipo='PADRAO',
            data_inicio=date(2030, 1, 11),
            hora_inicio=time(11, 0),
            cert_team_bg_path='file/fundo_padrao.png',
        )
        db.session.add(event)
        db.session.commit()

        service = CertificateService()
        bootstrap = service.build_designer_bootstrap(event, designer_mode='team_event')

        assert bootstrap['designer_mode'] == 'team_event'
        assert bootstrap['template']['version'] == 2
        assert any(item['id'] == 'name_fixed' for item in bootstrap['fixed_validation_elements'])
        assert '{{PAPEL}}' in json.dumps(bootstrap['preview_data'], ensure_ascii=False)
```

- [ ] **Step 4: Run the team bootstrap test to verify it fails**

Run: `python -m pytest tests/test_services.py::test_certificate_service_build_designer_bootstrap_supports_team_event_mode -q`

Expected: FAIL because `build_designer_bootstrap` does not exist yet.

- [ ] **Step 5: Implement the common bootstrap and fallback contract**

Em `app/services/certificate_service.py`, adicionar metodos pequenos e diretos na classe `CertificateService`:

```python
    @classmethod
    def _background_for_entity(cls, event, designer_mode='event'):
        if designer_mode == 'team_event':
            return getattr(event, 'cert_team_bg_path', '') or ''
        return getattr(event, 'cert_bg_path', '') or ''

    @classmethod
    def _template_json_for_entity(cls, event, designer_mode='event'):
        if designer_mode == 'team_event':
            return getattr(event, 'cert_team_template_json', None)
        return getattr(event, 'cert_template_json', None)

    @classmethod
    def build_preview_data(cls, event, designer_mode='event'):
        base = {
            '{{NOME}}': 'Participante Preview',
            '{{CPF}}': '123.456.789-00',
            '{{EVENTO}}': getattr(event, 'nome', '') or 'Evento Preview',
            '{{ATIVIDADE}}': 'Atividade Preview',
            '{{HORAS}}': '4',
            '{{DATA}}': current_certificate_issue_date_label(),
            '{{DATA_REALIZACAO}}': current_certificate_issue_date_label(),
            '{{HASH}}': 'PREVIEWHASH0001',
        }
        if designer_mode == 'team_event':
            return {
                **base,
                '{{NOME}}': 'Integrante Preview',
                '{{PAPEL}}': 'Palestrante',
            }
        return base

    @classmethod
    def build_default_template(cls, designer_mode='event', bg=''):
        text = (
            'Certificamos que {{RECIPIENT_NAME}} participou como {{CATEGORY}} do curso {{CURSO_USUARIO}}, com carga horária de {{CARGA_HORARIA}} horas.'
            if designer_mode == 'institutional'
            else (
                'Certificamos que {{NOME}}, CPF {{CPF}}, atuou como {{PAPEL}} no evento {{EVENTO}} na data {{DATA_REALIZACAO}} com carga horária de {{HORAS}}.'
                if designer_mode == 'team_event'
                else 'Certificamos que {{NOME}}, CPF {{CPF}}, participou do evento {{EVENTO}} na data {{DATA_REALIZACAO}} com carga horária de {{HORAS}} horas.'
            )
        )
        return {
            'version': 2,
            'document': {'gridSize': 2, 'snap': True, 'guides': True},
            'bg': str(bg or '').strip(),
            'elements': [
                {
                    'id': 'txt2',
                    'type': 'text',
                    'text': text,
                    'x': 50,
                    'y': 50,
                    'w': 82 if designer_mode != 'institutional' else 80,
                    'h': 24,
                    'font': 22,
                    'color': '#334155',
                    'align': 'center',
                    'bold': False,
                    'italic': False,
                    'font_family': 'Helvetica',
                    'zIndex': 3,
                    'locked': False,
                    'visible': True,
                }
            ] + json.loads(json.dumps(cls.get_fixed_validation_elements(designer_mode=designer_mode))),
        }

    @classmethod
    def build_designer_bootstrap(cls, event, designer_mode='event'):
        bg = cls._background_for_entity(event, designer_mode=designer_mode)
        default_template = cls.build_default_template(designer_mode=designer_mode, bg=bg)
        warnings = []
        raw_template = cls._template_json_for_entity(event, designer_mode=designer_mode)

        if raw_template:
            try:
                parsed = json.loads(raw_template)
                normalized = cls.normalize_template_payload(parsed, designer_mode=designer_mode)
            except Exception:
                normalized = cls.normalize_template_payload(default_template, designer_mode=designer_mode)
                warnings.append({'code': 'template_fallback_invalid_json', 'message': 'Template salvo invalido; fallback aplicado.'})
        else:
            normalized = cls.normalize_template_payload(default_template, designer_mode=designer_mode)

        return {
            'designer_mode': designer_mode,
            'entity_id': getattr(event, 'id', None),
            'template': normalized,
            'background': normalized.get('bg') or bg,
            'fixed_validation_elements': cls.get_fixed_validation_elements(designer_mode=designer_mode),
            'preview_data': cls.build_preview_data(event, designer_mode=designer_mode),
            'warnings': warnings,
        }
```

Tambem ajustar `_parse_template_elements()` para ler `cert_team_template_json` e `cert_team_bg_path` quando `designer_mode == 'team_event'`, substituindo os usos diretos de `event.cert_template_json` e `event.cert_bg_path` por `_template_json_for_entity()` e `_background_for_entity()`.

- [ ] **Step 6: Run both new service tests to verify they pass**

Run: `python -m pytest tests/test_services.py::test_certificate_service_build_designer_bootstrap_falls_back_when_event_template_is_invalid tests/test_services.py::test_certificate_service_build_designer_bootstrap_supports_team_event_mode -q`

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add app/services/certificate_service.py tests/test_services.py
git commit -m "feat(certificates): add unified designer bootstrap contract"
```

Expected: commit created successfully.

## Task 2: Migrar O Designer Para Consumir Bootstrap E Mostrar Falhas

**Files:**
- Modify: `app/api/certificates.py`
- Modify: `app/main/routes.py`
- Modify: `app/templates/certificate_designer.html`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing API test for the participant bootstrap endpoint**

Adicionar em `tests/test_api.py`, perto dos testes do designer:

```python
def test_certificate_designer_bootstrap_returns_normalized_template_and_warnings(client, app, admin_user):
    _login_admin(client)
    event_id = _create_event_for_certs(app)

    with app.app_context():
        event = db.session.get(Event, event_id)
        event.cert_template_json = '{"broken": '
        db.session.commit()

    res = client.get(f'/api/certificates/bootstrap/{event_id}')

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['designer_mode'] == 'event'
    assert payload['template']['version'] == 2
    assert payload['template']['elements']
    assert payload['warnings']
```

- [ ] **Step 2: Run the participant bootstrap test to verify it fails**

Run: `python -m pytest tests/test_api.py::test_certificate_designer_bootstrap_returns_normalized_template_and_warnings -q`

Expected: FAIL because `/api/certificates/bootstrap/<event_id>` does not exist yet.

- [ ] **Step 3: Write the failing API test for the team bootstrap endpoint**

Adicionar em `tests/test_api.py`, logo abaixo:

```python
def test_team_certificate_designer_bootstrap_returns_team_mode_payload(client, app, admin_user):
    seeded = _seed_certificate_management_data(app)
    _login_user(client, seeded['owner_username'])

    res = client.get(f"/api/certificates/team/event/{seeded['event_id']}/bootstrap")

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['designer_mode'] == 'team_event'
    assert payload['template']['version'] == 2
    assert '{{PAPEL}}' in json.dumps(payload['preview_data'], ensure_ascii=False)
```

- [ ] **Step 4: Run the team bootstrap test to verify it fails**

Run: `python -m pytest tests/test_api.py::test_team_certificate_designer_bootstrap_returns_team_mode_payload -q`

Expected: FAIL because `/api/certificates/team/event/<event_id>/bootstrap` does not exist yet.

- [ ] **Step 5: Implement the bootstrap endpoints and template changes**

Em `app/api/certificates.py`, adicionar endpoints simples que reutilizam `CertificateService.build_designer_bootstrap()`:

```python
@bp.route('/bootstrap/<int:event_id>', methods=['GET'])
@login_required
def certificate_designer_bootstrap(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_view_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    payload = cert_service.build_designer_bootstrap(event, designer_mode='event')
    payload['permissions'] = {
        'can_manage_certificates': _can_manage_certificates(event),
        'can_view_certificates': True,
    }
    payload['recipient_scope'] = 'event_participants'
    return jsonify(payload)


@bp.route('/team/event/<int:event_id>/bootstrap', methods=['GET'])
@login_required
def team_certificate_designer_bootstrap(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_view_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    payload = cert_service.build_designer_bootstrap(event, designer_mode='team_event')
    payload['permissions'] = {
        'can_manage_certificates': _can_manage_certificates(event),
        'can_view_certificates': True,
    }
    payload['recipient_scope'] = 'event_team_resolved'
    return jsonify(payload)
```

Em `app/main/routes.py`, simplificar o `designer_certificado_equipe()` para passar o evento real ao template, sem `SimpleNamespace`, e trocar os `fixed_validation_elements` para o modo correto:

```python
    return render_template(
        'certificate_designer.html',
        user=current_user,
        event=event,
        designer_mode='team_event',
        can_manage_certificates=can_manage_certificates,
        fixed_validation_elements=CertificateService.get_fixed_validation_elements(designer_mode='team_event'),
    )
```

Em `app/templates/certificate_designer.html`, substituir a inicializacao baseada em `persistedTemplateRaw` por bootstrap remoto:

```javascript
    const bootstrapUrl = designerMode === 'team_event'
        ? apiUrl(`/api/certificates/team/event/${entityId}/bootstrap`)
        : (designerMode === 'institutional'
            ? null
            : apiUrl(`/api/certificates/bootstrap/${entityId}`));

    async function fetchDesignerBootstrap() {
        if (designerMode === 'institutional') {
            return {
                template: JSON.parse(JSON.stringify(defaultTemplate)),
                fixed_validation_elements: fixedValidationElements,
                preview_data: buildRandomPreviewData(),
                warnings: [],
            };
        }

        const response = await fetch(bootstrapUrl, { cache: 'no-store' });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.erro || 'Nao foi possivel carregar o bootstrap do designer.');
        }
        return payload;
    }
```

e trocar o `boot()` para:

```javascript
    async function boot() {
        designer = new fabric.Canvas('certCanvas', {
            width: W,
            height: H,
            preserveObjectStacking: true,
            selection: true
        });

        try {
            const bootstrap = await fetchDesignerBootstrap();
            template = applyTemplateDefaults(bootstrap.template || defaultTemplate);
            if (Array.isArray(bootstrap.warnings) && bootstrap.warnings.length) {
                Toast.fire({ icon: 'warning', title: bootstrap.warnings[0].message || 'Layout aberto com fallback seguro.' });
            }
        } catch (error) {
            template = JSON.parse(JSON.stringify(defaultTemplate));
            Toast.fire({ icon: 'error', title: error.message || 'Falha ao abrir o designer. Fallback local aplicado.' });
        }

        bgPath = template.bg || '';
        await loadBackground(bgPath);
        await applyTemplateOnCanvas(template);
        renderGridOverlay();
        renderRulerLabels();
        setupDesignerEvents();
        setupKeyboardShortcuts();
        syncControlsFromTemplate();
        syncAutoFitToggle();
    }
```

- [ ] **Step 6: Run the two new bootstrap API tests to verify they pass**

Run: `python -m pytest tests/test_api.py::test_certificate_designer_bootstrap_returns_normalized_template_and_warnings tests/test_api.py::test_team_certificate_designer_bootstrap_returns_team_mode_payload -q`

Expected: PASS.

- [ ] **Step 7: Run a focused designer regression subset**

Run: `python -m pytest tests/test_api.py::test_certificate_designer_default_script_removes_participation_title tests/test_api.py::test_certificate_preview_layout_returns_pdf tests/test_api.py::test_team_certificate_pages_load_for_owner_and_gestor tests/test_api.py::test_team_certificate_designer_setup_and_preview_return_pdf -q`

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add app/api/certificates.py app/main/routes.py app/templates/certificate_designer.html tests/test_api.py
git commit -m "feat(certificates): bootstrap unified certificate designer"
```

Expected: commit created successfully.

## Task 3: Resolver Destinatarios De Equipe Por Atividade E Responsaveis

**Files:**
- Modify: `app/services/event_team_certificate_service.py`
- Modify: `app/api/certificates.py`
- Modify: `app/templates/team_certificate_delivery.html`
- Test: `tests/test_services.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing service test for resolved team recipients across activities and responsibles**

Adicionar em `tests/test_services.py`, perto dos testes de `EventTeamCertificateService`:

```python
def test_event_team_certificate_service_resolves_activity_and_responsible_recipients(app):
    from app.models import ActivitySpeaker

    with app.app_context():
        service = EventService()
        event = service.create_event('admin_test', {
            'nome': 'Evento Resolver Equipe',
            'descricao': 'Desc',
            'tipo': 'PADRAO',
            'data_inicio': '2030-01-20',
            'hora_inicio': '10:00',
            'atividades': [
                {
                    'nome': 'Atividade A',
                    'descricao': 'A',
                    'data_atv': '2030-01-20',
                    'hora_atv': '10:00',
                    'carga_horaria': 4,
                    'vagas': 20,
                },
                {
                    'nome': 'Atividade B',
                    'descricao': 'B',
                    'data_atv': '2030-01-20',
                    'hora_atv': '14:00',
                    'carga_horaria': 2,
                    'vagas': 20,
                },
            ],
        })
        activity_a, activity_b = event.activities
        db.session.add_all([
            ActivitySpeaker(activity_id=activity_a.id, nome='Pessoa Repetida', email='speaker@test.local', ordem=0),
            ActivitySpeaker(activity_id=activity_b.id, nome='Pessoa Repetida', email='speaker@test.local', ordem=0),
        ])
        db.session.commit()

        resolver = EventTeamCertificateService()
        recipients = resolver.resolve_event_recipients(event)

        assert len([item for item in recipients if item['source'] == 'activity']) == 2
        assert any(item['source'] == 'responsible' for item in recipients)
```

- [ ] **Step 2: Run the resolver service test to verify it fails**

Run: `python -m pytest tests/test_services.py::test_event_team_certificate_service_resolves_activity_and_responsible_recipients -q`

Expected: FAIL because `resolve_event_recipients` does not exist yet.

- [ ] **Step 3: Write the failing API test for the resolved team delivery list**

Adicionar em `tests/test_api.py`, perto dos testes de equipe:

```python
def test_team_certificate_delivery_list_returns_resolved_activity_and_responsible_rows(client, app, admin_user):
    seeded = _seed_certificate_management_data(app)

    with app.app_context():
        from app.models import ActivitySpeaker
        db.session.add(ActivitySpeaker(
            activity_id=seeded['activity_id'],
            nome='Palestrante Resolvido',
            email='resolved.speaker@test.local',
            ordem=0,
        ))
        db.session.commit()

    _login_user(client, seeded['owner_username'])
    res = client.get(f"/api/certificates/team/event/{seeded['event_id']}/recipients")

    assert res.status_code == 200
    payload = res.get_json()
    assert payload['total'] >= 2
    assert any(item['source'] == 'activity' for item in payload['items'])
    assert any(item['source'] == 'responsible' for item in payload['items'])
```

- [ ] **Step 4: Run the resolved API test to verify it fails**

Run: `python -m pytest tests/test_api.py::test_team_certificate_delivery_list_returns_resolved_activity_and_responsible_rows -q`

Expected: FAIL because the list currently reflects only persisted `EventTeamCertificateRecipient` rows.

- [ ] **Step 5: Implement the team recipient resolver and resolved API list**

Em `app/services/event_team_certificate_service.py`, adicionar um resolver explicito:

```python
    def resolve_event_recipients(self, event):
        resolved = []

        for activity in event.activities:
            for speaker in activity.speakers:
                speaker_name = (speaker.nome or '').strip()
                if not speaker_name:
                    continue
                resolved.append({
                    'event_id': event.id,
                    'activity_id': activity.id,
                    'activity_name': activity.nome,
                    'nome': speaker_name,
                    'email': (speaker.email or '').strip() or None,
                    'cpf': None,
                    'role_label': 'Palestrante',
                    'workload_hours': self.normalize_workload_hours(activity.carga_horaria),
                    'source': 'activity',
                })

        for responsible in event.responsibles:
            user = responsible.user
            if not user or not (user.nome or '').strip():
                continue
            resolved.append({
                'event_id': event.id,
                'activity_id': None,
                'activity_name': None,
                'nome': user.nome,
                'email': (user.email or '').strip() or None,
                'cpf': user.cpf,
                'role_label': 'Responsavel pelo evento' if responsible.is_primary else 'Equipe organizadora',
                'workload_hours': None,
                'source': 'responsible',
            })

        manual_rows = EventTeamCertificateRecipient.query.filter_by(event_id=event.id, source='manual').all()
        for item in manual_rows:
            resolved.append({
                'id': item.id,
                'event_id': item.event_id,
                'activity_id': item.activity_id,
                'activity_name': item.activity.nome if item.activity else None,
                'nome': item.nome,
                'email': item.email,
                'cpf': item.cpf,
                'role_label': item.role_label,
                'workload_hours': item.workload_hours,
                'source': 'manual',
                'cert_hash': item.cert_hash,
                'cert_entregue': item.cert_entregue,
                'cert_data_envio': item.cert_data_envio,
            })

        return resolved
```

No mesmo servico, adicionar uma chave estavel por linha resolvida para suportar preview/download/reenvio sem depender apenas de `recipient_id` persistido:

```python
    @staticmethod
    def build_resolved_key(row):
        return '|'.join([
            str(row.get('source') or ''),
            str(row.get('event_id') or ''),
            str(row.get('activity_id') or ''),
            str(row.get('nome') or ''),
            str(row.get('email') or ''),
            str(row.get('role_label') or ''),
        ])
```

Em `app/api/certificates.py`, alterar `list_team_recipients()` para usar `resolve_event_recipients(event)` e padronizar o payload final em vez de consultar apenas `EventTeamCertificateRecipient.query.filter_by(event_id=event_id)`.

Usar um payload explicito neste formato:

```python
    return jsonify({
        'items': [
            {
                'id': item.get('id'),
                'nome': item.get('nome'),
                'email': item.get('email'),
                'cpf': item.get('cpf'),
                'role_label': item.get('role_label'),
                'activity_id': item.get('activity_id'),
                'activity_name': item.get('activity_name'),
                'workload_hours': item.get('workload_hours'),
                'source': item.get('source'),
                'resolved_key': team_cert_service.build_resolved_key(item),
                'cert_hash': item.get('cert_hash'),
                'cert_entregue': bool(item.get('cert_entregue')),
                'cert_data_envio': item.get('cert_data_envio').strftime('%d/%m/%Y %H:%M') if item.get('cert_data_envio') else 'Pendente',
            }
            for item in team_cert_service.resolve_event_recipients(event)
        ],
        'total': len(team_cert_service.resolve_event_recipients(event)),
    })
```

Em `app/templates/team_certificate_delivery.html`, ajustar a renderizacao para explicitar a origem:

```javascript
                        <td>
                            <span class="fw-semibold">${escapeHtml(item.role_label)}</span>
                            <div class="text-muted x-small">Origem: ${escapeHtml(item.source || '-')}</div>
                        </td>
```

e condicionar as acoes manuais para nao tentar editar/excluir linhas automaticas sem `id` persistido:

```javascript
const manualActions = item.source === 'manual' && item.id
    ? `<button onclick="abrirModalEditar(${item.id}, ${jsArg(item.nome)}, ${jsArg(item.role_label)}, ${jsArg(item.email)}, ${jsArg(item.cpf)}, ${jsArg(String(item.activity_id || ''))}, ${jsArg(String(item.workload_hours || ''))})" class="btn btn-sm btn-light border" title="Editar">
            <i class="fa-solid fa-pen"></i>
       </button>
       <button onclick="confirmarExcluir(${item.id})" class="btn btn-sm btn-light border text-danger" title="Excluir">
            <i class="fa-solid fa-trash-can"></i>
       </button>`
    : '';
```

e trocar preview/download/envio para rotas resolvidas baseadas em `resolved_key`:

```javascript
<button onclick="abrirPreviewEquipe(item.resolved_key)" class="btn btn-sm btn-light border" title="Visualizar">
    <i class="fa-solid fa-eye text-primary"></i>
</button>
<a href="${apiUrl('/api/certificates/team/resolved/' + encodeURIComponent(item.resolved_key) + '/download')}" class="btn btn-sm btn-light border" title="Baixar PDF">
    <i class="fa-solid fa-file-pdf text-danger"></i>
</a>
<button onclick="enviarIndividual(item.resolved_key)" class="btn btn-sm btn-outline-primary rounded-end px-3">
    <i class="fa-solid fa-paper-plane me-1"></i> ${item.cert_entregue ? 'Reenviar' : 'Enviar'}
</button>
```

e usar `${manualActions}` dentro do `btn-group`, mantendo edit/delete apenas para linhas manuais.

e trocar a mensagem vazia para:

```javascript
tbody.innerHTML = '<tr><td colspan="6" class="text-center py-5 text-muted">Nenhum destinatario resolvido a partir de atividades, responsaveis ou complementos manuais.</td></tr>';
```

- [ ] **Step 6: Run the two new resolver tests to verify they pass**

Run: `python -m pytest tests/test_services.py::test_event_team_certificate_service_resolves_activity_and_responsible_recipients tests/test_api.py::test_team_certificate_delivery_list_returns_resolved_activity_and_responsible_rows -q`

Expected: PASS.

- [ ] **Step 7: Run focused team regressions**

Run: `python -m pytest tests/test_api.py::test_team_certificate_sync_and_manual_crud tests/test_api.py::test_team_certificate_pages_load_for_owner_and_gestor tests/test_api.py::test_team_certificate_delivery_page_safe_with_special_chars -q`

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add app/services/event_team_certificate_service.py app/api/certificates.py app/templates/team_certificate_delivery.html tests/test_services.py tests/test_api.py
git commit -m "feat(certificates): resolve team recipients from activities"
```

Expected: commit created successfully.

## Task 4: Usar A Lista Resolvida Em Preview E Envio De Equipe E Validar Tudo

**Files:**
- Modify: `app/services/event_team_certificate_service.py`
- Modify: `app/api/certificates.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing API test for duplicate activity certificates in team batch**

Adicionar em `tests/test_api.py`, perto dos testes de batch de equipe:

```python
def test_team_certificate_send_batch_uses_resolved_activity_rows(client, app, admin_user, monkeypatch, tmp_path):
    seeded = _seed_certificate_management_data(app)
    pdf_path = tmp_path / 'resolved-team-batch.pdf'
    pdf_path.write_bytes(b'%PDF-1.4\n% mocked resolved team batch\n')
    sent = []

    with app.app_context():
        from app.models import ActivitySpeaker
        db.session.add_all([
            ActivitySpeaker(activity_id=seeded['activity_id'], nome='Speaker 1', email='speaker1@test.local', ordem=0),
            ActivitySpeaker(activity_id=seeded['activity_id'], nome='Speaker 2', email='speaker2@test.local', ordem=1),
        ])
        db.session.commit()

    class ImmediateThread:
        def __init__(self, target=None, args=None, daemon=None):
            self.target = target
            self.args = args or ()
        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(certificates_api, 'Thread', ImmediateThread)
    monkeypatch.setattr(certificates_api.team_cert_service, 'generate_recipient_pdf', lambda *args, **kwargs: str(pdf_path))
    monkeypatch.setattr(certificates_api.team_cert_service.notifier, 'send_email_task', lambda **kwargs: sent.append(kwargs) or True)

    _login_user(client, seeded['owner_username'])
    res = client.post(f"/api/certificates/team/event/{seeded['event_id']}/send_batch")

    assert res.status_code == 202
    assert len(sent) >= 2
```

- [ ] **Step 2: Run the batch test to verify it fails**

Run: `python -m pytest tests/test_api.py::test_team_certificate_send_batch_uses_resolved_activity_rows -q`

Expected: FAIL because the batch currently iterates only persisted recipient rows.

- [ ] **Step 3: Write the failing API test for resolved preview and resend actions**

Adicionar em `tests/test_api.py`, logo abaixo:

```python
def test_team_certificate_resolved_preview_and_resend_accept_resolved_key(client, app, admin_user, monkeypatch, tmp_path):
    seeded = _seed_certificate_management_data(app)
    pdf_path = tmp_path / 'resolved-preview.pdf'
    pdf_path.write_bytes(b'%PDF-1.4\n% mocked resolved preview\n')
    sent = []

    with app.app_context():
        from app.models import ActivitySpeaker
        db.session.add(ActivitySpeaker(
            activity_id=seeded['activity_id'],
            nome='Speaker Preview',
            email='speaker.preview@test.local',
            ordem=0,
        ))
        db.session.commit()
        event = db.session.get(Event, seeded['event_id'])
        resolved = certificates_api.team_cert_service.resolve_event_recipients(event)
        resolved_row = next(item for item in resolved if item['source'] == 'activity')
        resolved_key = certificates_api.team_cert_service.build_resolved_key(resolved_row)

    monkeypatch.setattr(certificates_api.team_cert_service, 'generate_recipient_pdf', lambda *args, **kwargs: str(pdf_path))
    monkeypatch.setattr(certificates_api.team_cert_service.notifier, 'send_email_task', lambda **kwargs: sent.append(kwargs) or True)

    _login_user(client, seeded['owner_username'])
    preview_res = client.get(f"/api/certificates/team/resolved/{resolved_key}/preview")
    resend_res = client.post(f"/api/certificates/team/resolved/{resolved_key}/resend")

    assert preview_res.status_code == 200
    assert preview_res.mimetype == 'application/pdf'
    assert resend_res.status_code == 200
    assert sent
```

- [ ] **Step 4: Run the resolved preview/resend test to verify it fails**

Run: `python -m pytest tests/test_api.py::test_team_certificate_resolved_preview_and_resend_accept_resolved_key -q`

Expected: FAIL because the resolved action endpoints do not exist yet.

- [ ] **Step 5: Implement resolved preview/send behavior for team certificates**

Em `app/services/event_team_certificate_service.py`, adicionar um helper de materializacao leve para as entradas resolvidas nao manuais:

```python
    def build_virtual_recipient(self, event, resolved_row):
        activity = next((item for item in event.activities if item.id == resolved_row.get('activity_id')), None)
        return SimpleNamespace(
            id=resolved_row.get('id') or 0,
            nome=resolved_row.get('nome') or '',
            email=resolved_row.get('email') or '',
            cpf=resolved_row.get('cpf') or '',
            role_label=resolved_row.get('role_label') or '',
            workload_hours=resolved_row.get('workload_hours'),
            cert_hash=resolved_row.get('cert_hash') or self.build_hash(event.id, resolved_row.get('nome'), resolved_row.get('role_label'), resolved_row.get('email')),
            activity=activity,
            cert_entregue=bool(resolved_row.get('cert_entregue')),
            cert_data_envio=resolved_row.get('cert_data_envio'),
        )
```

Em `app/api/certificates.py`, adicionar um helper para localizar uma linha resolvida a partir de `resolved_key`:

```python
def _resolved_team_row_or_404(event, resolved_key):
    for item in team_cert_service.resolve_event_recipients(event):
        if item['resolved_key'] == resolved_key:
            return item
    abort(404)
```

e criar os endpoints:

```python
@bp.route('/team/resolved/<path:resolved_key>/preview', methods=['GET'])
@login_required
def preview_resolved_team_recipient(resolved_key):
    event_id = int(resolved_key.split('|', 2)[1])
    event = _get_or_404(Event, event_id)
    if not _can_view_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    row = _resolved_team_row_or_404(event, resolved_key)
    recipient = team_cert_service.build_virtual_recipient(event, row)
    pdf_path = team_cert_service.generate_recipient_pdf(event, recipient)
    return _build_pdf_preview_response(pdf_path)


@bp.route('/team/resolved/<path:resolved_key>/download', methods=['GET'])
@login_required
def download_resolved_team_recipient(resolved_key):
    event_id = int(resolved_key.split('|', 2)[1])
    event = _get_or_404(Event, event_id)
    if not _can_view_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    row = _resolved_team_row_or_404(event, resolved_key)
    recipient = team_cert_service.build_virtual_recipient(event, row)
    pdf_path = team_cert_service.generate_recipient_pdf(event, recipient)
    return send_file(pdf_path, as_attachment=True, download_name=f"Certificado_Equipe_{recipient.nome.replace(' ', '_')}.pdf")


@bp.route('/team/resolved/<path:resolved_key>/resend', methods=['POST'])
@login_required
def resend_resolved_team_recipient(resolved_key):
    event_id = int(resolved_key.split('|', 2)[1])
    event = _get_or_404(Event, event_id)
    if not _can_manage_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    row = _resolved_team_row_or_404(event, resolved_key)
    recipient = team_cert_service.build_virtual_recipient(event, row)
    if not recipient.email:
        return jsonify({'erro': 'E-mail não definido para este destinatário.'}), 400
    pdf_path = team_cert_service.generate_recipient_pdf(event, recipient)
    team_cert_service.queue_email(event, recipient, pdf_path)
    return jsonify({'mensagem': 'Reenvio solicitado.'})
```

Tambem ajustar `_run_send_team_batch_job()` para iterar sobre `team_cert_service.resolve_event_recipients(event)` e, para linhas nao manuais, usar `team_cert_service.build_virtual_recipient(event, resolved_row)` antes de chamar `generate_recipient_pdf()` e `queue_email()`.

Tambem ajustar `preview_team_layout()` para chamar `_normalize_template_payload(..., designer_mode='team_event')` e `setup_team_certificate()` para normalizar com `designer_mode='team_event'`.

- [ ] **Step 6: Run the new batch and resolved action tests to verify they pass**

Run: `python -m pytest tests/test_api.py::test_team_certificate_send_batch_uses_resolved_activity_rows tests/test_api.py::test_team_certificate_resolved_preview_and_resend_accept_resolved_key -q`

Expected: PASS.

- [ ] **Step 7: Run the full focused certificate regression subset**

Run: `python -m pytest tests/test_api.py::test_certificate_preview_layout_returns_pdf tests/test_api.py::test_certificate_designer_bootstrap_returns_normalized_template_and_warnings tests/test_api.py::test_team_certificate_designer_bootstrap_returns_team_mode_payload tests/test_api.py::test_team_certificate_send_batch_runs_background_job tests/test_api.py::test_team_certificate_send_batch_uses_resolved_activity_rows tests/test_api.py::test_team_certificate_public_download_and_preview_by_hash -q`

Expected: PASS.

- [ ] **Step 8: Run the full test suite**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 9: Run final diff hygiene and workspace checks**

Run: `git diff --check && git status --short`

Expected: no diff hygiene output and only the intended tracked changes before any optional final commit.

- [ ] **Step 10: Commit Task 4**

Run:

```bash
git add app/services/event_team_certificate_service.py app/api/certificates.py tests/test_api.py
git commit -m "fix(certificates): unify team certificate resolution and delivery"
```

Expected: commit created successfully.
