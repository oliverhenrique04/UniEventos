# Atalho do Designer de Certificados da Equipe em `/eventos` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer com que o botão de certificados da equipe nas listagens de eventos abra diretamente `/designer_certificado_equipe/:id` no `dashboard` e em `events_admin`, com texto acessível coerente.

**Architecture:** A mudança é um ajuste de navegação puramente no cliente renderizado por templates Jinja/JS. O trabalho fica concentrado em dois templates que montam os atalhos dos cards/tabelas de eventos e em um teste de renderização já existente em `tests/test_api.py`, mantendo as rotas e permissões atuais intactas.

**Tech Stack:** Flask, Jinja templates com JavaScript inline, pytest

---

## File Structure

- Modify: `app/templates/dashboard.html:4157-4167`
  - Responsável pelos botões de ação nos cards de eventos do dashboard.
- Modify: `app/templates/events_admin.html:1517-1529`
  - Responsável pelos botões de ação na listagem administrativa de eventos.
- Modify: `tests/test_api.py:3363-3380`
  - Responsável por validar os links renderizados das páginas `/` e `/eventos_admin`.

### Task 1: Atualizar o teste de renderização para o novo destino da equipe

**Files:**
- Modify: `tests/test_api.py:3363-3380`
- Test: `tests/test_api.py::test_event_pages_expose_separate_team_certificate_access`

- [ ] **Step 1: Write the failing test**

Atualize `test_event_pages_expose_separate_team_certificate_access` para refletir o comportamento novo.

Substitua o bloco atual por este conteúdo:

```python
def test_event_pages_expose_separate_team_certificate_access(client, app, admin_user):
    seeded = _seed_certificate_management_data(app)

    _login_user(client, seeded['owner_username'])

    events_admin_res = client.get('/eventos_admin')
    dashboard_res = client.get('/')

    assert events_admin_res.status_code == 200
    events_admin_html = events_admin_res.get_data(as_text=True)
    assert '/designer_certificado/${ev.id}' in events_admin_html
    assert '/designer_certificado_equipe/${ev.id}' in events_admin_html
    assert 'Designer de Certificados da Equipe' in events_admin_html

    assert dashboard_res.status_code == 200
    dashboard_html = dashboard_res.get_data(as_text=True)
    assert '/designer_certificado/${ev.id}' in dashboard_html
    assert '/designer_certificado_equipe/${ev.id}' in dashboard_html
    assert 'Designer de Certificados da Equipe' in dashboard_html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_api.py::test_event_pages_expose_separate_team_certificate_access -q`

Expected: FAIL porque os templates ainda renderizam `/certificados_equipe/${ev.id}` e o `title` antigo `Certificados da Equipe`.

- [ ] **Step 3: Do not change production code yet**

Nenhuma alteração adicional nesta etapa. O objetivo é manter a falha vermelha confirmada antes da implementação.

- [ ] **Step 4: Re-run the same failing test if needed**

Run: `python3 -m pytest tests/test_api.py::test_event_pages_expose_separate_team_certificate_access -q`

Expected: FAIL novamente com asserção de link/tooltip ausente.

### Task 2: Trocar o atalho da equipe no dashboard para o designer da equipe

**Files:**
- Modify: `app/templates/dashboard.html:4161-4167`
- Test: `tests/test_api.py::test_event_pages_expose_separate_team_certificate_access`

- [ ] **Step 1: Write the minimal implementation in the dashboard**

Altere o bloco do botão da equipe em `app/templates/dashboard.html` para este trecho:

```html
${ev.can_view_certificates ? `
                                <a href="${pathUrl(`/designer_certificado/${ev.id}`)}" class="btn btn-sm btn-light border" title="Certificados de Participantes">
                                    <i class="fa-solid fa-certificate"></i>
                                </a>
                                <a href="${pathUrl(`/designer_certificado_equipe/${ev.id}`)}" class="btn btn-sm btn-light border" title="Designer de Certificados da Equipe">
                                    <i class="fa-solid fa-users"></i>
                                </a>` : ''}
```

- [ ] **Step 2: Run the targeted test to verify it still fails for `events_admin`**

Run: `python3 -m pytest tests/test_api.py::test_event_pages_expose_separate_team_certificate_access -q`

Expected: FAIL, agora apenas porque `events_admin.html` ainda contém `/certificados_equipe/${ev.id}` e o título antigo.

- [ ] **Step 3: Inspect the failure output**

Confirme no traceback que a falha restante vem do HTML de `events_admin_res`, não do dashboard. Não avance se a falha apontar outro problema.

### Task 3: Trocar o atalho da equipe em `events_admin` e fechar a regressão

**Files:**
- Modify: `app/templates/events_admin.html:1517-1529`
- Modify: `tests/test_api.py:3363-3380`
- Test: `tests/test_api.py::test_event_pages_expose_separate_team_certificate_access`

- [ ] **Step 1: Write the minimal implementation in `events_admin`**

Troque apenas o link e os textos acessíveis necessários no bloco de certificados:

```html
${ev.can_view_certificates ? `
                            <a href="${pathUrl(`/designer_certificado/${ev.id}`)}" class="btn btn-sm btn-light border d-flex align-items-center justify-content-center" title="Certificados de Participantes">
                                <i class="fa-solid fa-certificate text-warning"></i>
                            </a>
                            <a href="${pathUrl(`/designer_certificado_equipe/${ev.id}`)}" class="btn btn-sm btn-light border d-flex align-items-center justify-content-center" title="Designer de Certificados da Equipe">
                                <i class="fa-solid fa-users text-primary"></i>
                            </a>` : `
                            <button class="btn btn-sm btn-light border d-flex align-items-center justify-content-center" title="Certificado indisponível" disabled>
                                <i class="fa-solid fa-certificate text-muted"></i>
                            </button>
                            <button class="btn btn-sm btn-light border d-flex align-items-center justify-content-center" title="Designer de Certificados da Equipe indisponível" disabled>
                                <i class="fa-solid fa-users text-muted"></i>
                            </button>`}
```

- [ ] **Step 2: Run the targeted test to verify it passes**

Run: `python3 -m pytest tests/test_api.py::test_event_pages_expose_separate_team_certificate_access -q`

Expected: PASS

- [ ] **Step 3: Run the nearby certificate navigation regression tests**

Run: `python3 -m pytest tests/test_api.py::test_event_pages_expose_separate_team_certificate_access tests/test_api.py::test_team_certificate_pages_load_for_owner_and_gestor -q`

Expected: `2 passed`

- [ ] **Step 4: Run the full suite**

Run: `python3 -m pytest -q`

Expected: suite green, sem regressões.

- [ ] **Step 5: Commit**

```bash
git add app/templates/dashboard.html app/templates/events_admin.html tests/test_api.py
git commit -m "fix(events): open team certificate designer from event lists"
```

Expected: commit criado apenas com a troca dos atalhos e os testes correspondentes.

## Self-Review

- **Spec coverage:** o plano cobre a troca de destino em `dashboard` e `events_admin`, o ajuste de texto acessível e a atualização dos testes de renderização.
- **Placeholder scan:** não há `TODO`, `TBD` ou referências vagas; cada passo aponta arquivos, comandos e trechos concretos.
- **Type consistency:** os caminhos usados no plano (`/designer_certificado_equipe/${ev.id}`) correspondem aos templates e às rotas existentes em `app/main/routes.py`.
