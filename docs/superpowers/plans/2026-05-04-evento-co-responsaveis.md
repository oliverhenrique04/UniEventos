# Evento Co-Responsaveis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que eventos tenham um responsavel principal e varios co-responsaveis com a mesma permissao operacional.

**Architecture:** A nova tabela `event_responsibles` passa a ser a fonte de verdade para responsaveis do evento. `events.owner_username` continua existindo como espelho do responsavel principal para compatibilidade com fluxos legados.

**Tech Stack:** Flask, Flask-Login, Flask-SQLAlchemy, Alembic/Flask-Migrate, Jinja templates, JavaScript sem framework, pytest.

---

## File Structure

- Modify `app/models.py`: adicionar `EventResponsible`, relacionamentos em `Event` e `User`, e indices de integridade.
- Create `migrations/versions/a5b7c9d2e4f6_add_event_responsibles.py`: criar a tabela relacional e migrar `events.owner_username` como principal.
- Modify `app/services/event_service.py`: normalizar payload de responsaveis, sincronizar principal, atualizar permissoes, listagens e notificacoes.
- Modify `app/repositories/event_repository.py`: fazer `get_by_owner()` considerar qualquer responsavel vinculado.
- Modify `app/serializers.py`: serializar `responsavel_principal`, `responsaveis`, `owner` e `owner_name` derivados do principal.
- Modify `app/api/events.py`: aceitar payload `responsaveis`, criar endpoint de busca de responsaveis elegiveis e ajustar filtros de dashboard.
- Modify `app/main/routes.py`: enviar responsaveis iniciais para as telas de criacao e edicao.
- Create `app/templates/partials/event_responsibles_editor.html`: componente compartilhado de selecao, remocao e marcacao do principal.
- Modify `app/templates/event_create.html`: incluir o parcial e enviar `responsaveis` no payload.
- Modify `app/templates/event_edit.html`: incluir o parcial com responsaveis existentes e enviar `responsaveis` no payload.
- Modify `app/templates/events_admin.html`: mostrar principal e co-responsaveis na coluna de responsavel.
- Create `tests/test_event_responsibles.py`: cobrir modelo, validacoes, permissoes, listagens, serializacao e notificacoes.
- Modify `tests/test_api.py`: cobrir endpoint de opcoes e filtro de dashboard por co-responsavel.

## Payload Contract

Criacao e edicao passam a aceitar este campo opcional:

```json
{
  "responsaveis": [
    {"username": "prof_principal", "is_primary": true},
    {"username": "coord_evento", "is_primary": false}
  ]
}
```

Se `responsaveis` nao vier no payload, o backend cria ou preserva o responsavel principal a partir de `owner_username`.

---

### Task 1: Data Model And Migration

**Files:**
- Create: `tests/test_event_responsibles.py`
- Modify: `app/models.py`
- Create: `migrations/versions/a5b7c9d2e4f6_add_event_responsibles.py`

- [ ] **Step 1: Write the failing model test**

Create `tests/test_event_responsibles.py` with this initial content:

```python
from datetime import date, time

import pytest

from app.extensions import db
from app.models import Event, EventResponsible, User
from app.serializers import serialize_event
from app.services.event_service import EventService


def _persist_user(username, role='professor', cpf='90000000000', can_create_events=False, nome=None, email=None):
    user = User(
        username=username,
        role=role,
        nome=nome or username.replace('_', ' ').title(),
        cpf=cpf,
        email=email,
        can_create_events=can_create_events,
    )
    user.set_password('1234')
    db.session.add(user)
    db.session.flush()
    return user


def _event_payload(**overrides):
    payload = {
        'nome': 'Evento Co Responsavel',
        'descricao': 'Evento usado nos testes de co-responsaveis',
        'is_rapido': True,
        'carga_horaria_rapida': 2,
        'data_inicio': '2030-05-04',
        'hora_inicio': '10:00',
        'data_fim': '2030-05-04',
        'hora_fim': '12:00',
    }
    payload.update(overrides)
    return payload


def _responsible_state(event):
    return [
        (responsible.user_username, bool(responsible.is_primary))
        for responsible in event.responsibles
    ]


def test_event_responsible_model_links_event_and_user(app):
    owner = _persist_user(
        'model_owner_resp',
        role='professor',
        cpf='90000000001',
        can_create_events=True,
        nome='Responsavel Modelo',
    )
    event = Event(
        owner_username=owner.username,
        nome='Evento Modelo Responsavel',
        descricao='Desc',
        tipo='PADRAO',
        data_inicio=date(2030, 5, 4),
        hora_inicio=time(10, 0),
        data_fim=date(2030, 5, 4),
        hora_fim=time(12, 0),
    )
    event.responsibles.append(EventResponsible(user=owner, is_primary=True))

    db.session.add(event)
    db.session.commit()

    saved_event = db.session.get(Event, event.id)
    assert _responsible_state(saved_event) == [('model_owner_resp', True)]
    assert saved_event.responsibles[0].user.nome == 'Responsavel Modelo'
    assert owner.event_responsibilities[0].event_id == saved_event.id
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_event_responsibles.py::test_event_responsible_model_links_event_and_user -q
```

Expected: FAIL with `ImportError: cannot import name 'EventResponsible'`.

- [ ] **Step 3: Add model relationships**

In `app/models.py`, add this relationship inside `User` after `event_registrations`:

```python
    event_responsibilities = db.relationship(
        'EventResponsible',
        back_populates='user',
        cascade='all, delete-orphan',
        foreign_keys='EventResponsible.user_username',
    )
```

In `app/models.py`, add this relationship inside `Event` after `registrations`:

```python
    responsibles = db.relationship(
        'EventResponsible',
        back_populates='event',
        cascade='all, delete-orphan',
        order_by=lambda: (
            db.desc(EventResponsible.is_primary),
            EventResponsible.created_at,
            EventResponsible.user_username,
        ),
    )
```

In `app/models.py`, add this class immediately after `Event` and before `EventAllowedRole`:

```python
class EventResponsible(db.Model):
    """Represents one user responsible for managing an event."""
    __tablename__ = 'event_responsibles'

    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), primary_key=True)
    user_username = db.Column(db.String(50), db.ForeignKey('users.username'), primary_key=True)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    event = db.relationship('Event', back_populates='responsibles')
    user = db.relationship('User', back_populates='event_responsibilities', foreign_keys=[user_username])

    __table_args__ = (
        db.Index('ix_event_responsibles_event_id', 'event_id'),
        db.Index('ix_event_responsibles_user_username', 'user_username'),
        db.Index(
            'uq_event_responsibles_single_primary',
            'event_id',
            unique=True,
            sqlite_where=db.text('is_primary = 1'),
            postgresql_where=db.text('is_primary = true'),
        ),
    )
```

- [ ] **Step 4: Add the Alembic migration**

Create `migrations/versions/a5b7c9d2e4f6_add_event_responsibles.py`:

```python
"""Add event responsibles

Revision ID: a5b7c9d2e4f6
Revises: c2f9e6a1b4d3
Create Date: 2026-05-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5b7c9d2e4f6'
down_revision = 'c2f9e6a1b4d3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'event_responsibles',
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_username', sa.String(length=50), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.ForeignKeyConstraint(['user_username'], ['users.username']),
        sa.PrimaryKeyConstraint('event_id', 'user_username'),
    )
    op.create_index('ix_event_responsibles_event_id', 'event_responsibles', ['event_id'], unique=False)
    op.create_index('ix_event_responsibles_user_username', 'event_responsibles', ['user_username'], unique=False)
    op.create_index(
        'uq_event_responsibles_single_primary',
        'event_responsibles',
        ['event_id'],
        unique=True,
        sqlite_where=sa.text('is_primary = 1'),
        postgresql_where=sa.text('is_primary = true'),
    )

    bind = op.get_bind()
    metadata = sa.MetaData()
    events = sa.Table('events', metadata, autoload_with=bind)
    users = sa.Table('users', metadata, autoload_with=bind)
    event_responsibles = sa.Table(
        'event_responsibles',
        metadata,
        sa.Column('event_id', sa.Integer()),
        sa.Column('user_username', sa.String(length=50)),
        sa.Column('is_primary', sa.Boolean()),
    )

    events_without_owner = bind.execute(
        sa.select(events.c.id).where(events.c.owner_username.is_(None))
    ).mappings().all()
    if events_without_owner:
        event_ids = ', '.join(str(row['id']) for row in events_without_owner)
        raise RuntimeError(
            f'Eventos sem owner_username impedem a migracao de responsaveis: {event_ids}'
        )

    missing_owner_rows = bind.execute(
        sa.select(events.c.id, events.c.owner_username)
        .select_from(events.outerjoin(users, users.c.username == events.c.owner_username))
        .where(events.c.owner_username.is_not(None), users.c.username.is_(None))
    ).mappings().all()
    if missing_owner_rows:
        details = ', '.join(
            f"evento {row['id']} -> {row['owner_username']}" for row in missing_owner_rows
        )
        raise RuntimeError(
            f'Eventos com owner_username inexistente impedem a migracao de responsaveis: {details}'
        )

    owner_rows = bind.execute(
        sa.select(events.c.id, events.c.owner_username).where(events.c.owner_username.is_not(None))
    ).mappings().all()
    if owner_rows:
        op.bulk_insert(
            event_responsibles,
            [
                {
                    'event_id': row['id'],
                    'user_username': row['owner_username'],
                    'is_primary': True,
                }
                for row in owner_rows
            ],
        )

    with op.batch_alter_table('event_responsibles', schema=None) as batch_op:
        batch_op.alter_column('is_primary', server_default=None)


def downgrade():
    op.drop_index('uq_event_responsibles_single_primary', table_name='event_responsibles')
    op.drop_index('ix_event_responsibles_user_username', table_name='event_responsibles')
    op.drop_index('ix_event_responsibles_event_id', table_name='event_responsibles')
    op.drop_table('event_responsibles')
```

- [ ] **Step 5: Run the model test and migration history check**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_event_responsibles.py::test_event_responsible_model_links_event_and_user -q
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m flask db heads
```

Expected: pytest PASS. `flask db heads` lists `a5b7c9d2e4f6 (head)`.

- [ ] **Step 6: Commit Task 1**

```powershell
git add app/models.py migrations/versions/a5b7c9d2e4f6_add_event_responsibles.py tests/test_event_responsibles.py
git commit -m "feat: add event responsibles model"
```

---

### Task 2: Responsible Validation And Synchronization

**Files:**
- Modify: `tests/test_event_responsibles.py`
- Modify: `app/services/event_service.py`

- [ ] **Step 1: Add failing service behavior tests**

Append these tests to `tests/test_event_responsibles.py`:

```python
def test_create_event_accepts_primary_and_co_responsible(app, admin_user):
    owner = db.session.get(User, admin_user.username)
    co_responsible = _persist_user(
        'create_co_resp',
        role='professor',
        cpf='90000000002',
        can_create_events=True,
        nome='Co Responsavel Criacao',
    )

    event = EventService().create_event(owner.username, _event_payload(
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': co_responsible.username, 'is_primary': False},
        ]
    ))

    assert event.owner_username == owner.username
    assert _responsible_state(event) == [
        (owner.username, True),
        ('create_co_resp', False),
    ]


def test_create_event_defaults_current_user_as_primary_responsible(app, admin_user):
    owner = db.session.get(User, admin_user.username)

    event = EventService().create_event(owner.username, _event_payload())

    assert event.owner_username == owner.username
    assert _responsible_state(event) == [(owner.username, True)]


def test_update_event_replaces_responsibles_and_syncs_primary_owner(app, admin_user):
    owner = db.session.get(User, admin_user.username)
    first_co = _persist_user('update_first_co_resp', role='gestor', cpf='90000000003')
    second_co = _persist_user('update_second_co_resp', role='coordenador', cpf='90000000004')

    service = EventService()
    event = service.create_event(owner.username, _event_payload(
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': first_co.username, 'is_primary': False},
        ]
    ))

    updated_event, message = service.update_event(event.id, owner, _event_payload(
        id=event.id,
        nome='Evento com Novo Principal',
        responsaveis=[
            {'username': first_co.username, 'is_primary': False},
            {'username': second_co.username, 'is_primary': True},
        ],
    ))

    assert message == 'Evento atualizado com sucesso!'
    assert updated_event.owner_username == second_co.username
    assert _responsible_state(updated_event) == [
        ('update_second_co_resp', True),
        ('update_first_co_resp', False),
    ]


@pytest.mark.parametrize(
    ('responsaveis', 'expected_message'),
    [
        ([], 'Informe ao menos um responsável pelo evento.'),
        ([{'username': 'admin_test', 'is_primary': False}], 'Selecione exatamente um responsável principal.'),
        ([{'username': 'admin_test', 'is_primary': True}, {'username': 'admin_test', 'is_primary': False}], 'Responsável duplicado: admin_test.'),
        ([{'username': 'missing_user', 'is_primary': True}], 'Usuário responsável não encontrado: missing_user.'),
    ],
)
def test_create_event_validates_responsibles_payload(app, admin_user, responsaveis, expected_message):
    owner = db.session.get(User, admin_user.username)

    with pytest.raises(ValueError, match=expected_message):
        EventService().create_event(owner.username, _event_payload(responsaveis=responsaveis))


def test_create_event_rejects_ineligible_responsible(app, admin_user):
    owner = db.session.get(User, admin_user.username)
    participant = _persist_user(
        'participant_not_responsible',
        role='participante',
        cpf='90000000005',
        can_create_events=False,
    )

    with pytest.raises(ValueError, match='Usuário sem permissão para ser responsável pelo evento: participant_not_responsible.'):
        EventService().create_event(owner.username, _event_payload(
            responsaveis=[
                {'username': owner.username, 'is_primary': True},
                {'username': participant.username, 'is_primary': False},
            ]
        ))
```

- [ ] **Step 2: Run the service tests and verify they fail**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_event_responsibles.py -q
```

Expected: FAIL because `EventService.create_event()` does not read `responsaveis` and does not populate `event.responsibles`.

- [ ] **Step 3: Import the new model in the service**

In `app/services/event_service.py`, add `EventResponsible` to the existing `from app.models import (...)` block:

```python
    EventResponsible,
```

- [ ] **Step 4: Add normalization and synchronization helpers**

In `app/services/event_service.py`, insert this block immediately after `_sync_event_registration_categories`:

```python
    @staticmethod
    def _is_user_eligible_as_event_responsible(user):
        return EventService.can_access_event_management(user)

    def _normalize_event_responsibles_payload(self, raw_responsibles, default_primary_username=None):
        if raw_responsibles is None:
            raw_responsibles = []

        if not isinstance(raw_responsibles, list):
            raise ValueError('Informe a lista de responsáveis do evento.')

        normalized = []
        seen = set()
        primary_count = 0

        for raw_item in raw_responsibles:
            if isinstance(raw_item, str):
                username = raw_item.strip()
                is_primary = False
            elif isinstance(raw_item, dict):
                username = str(
                    raw_item.get('username')
                    or raw_item.get('user_username')
                    or ''
                ).strip()
                is_primary = bool(raw_item.get('is_primary'))
            else:
                continue

            if not username:
                continue
            if username in seen:
                raise ValueError(f'Responsável duplicado: {username}.')

            seen.add(username)
            if is_primary:
                primary_count += 1
            normalized.append({
                'username': username,
                'is_primary': is_primary,
            })

        default_primary_username = str(default_primary_username or '').strip() or None
        if default_primary_username and default_primary_username not in seen:
            normalized.insert(0, {
                'username': default_primary_username,
                'is_primary': primary_count == 0,
            })
            seen.add(default_primary_username)
            if primary_count == 0:
                primary_count = 1

        if not normalized:
            raise ValueError('Informe ao menos um responsável pelo evento.')
        if primary_count != 1:
            raise ValueError('Selecione exatamente um responsável principal.')

        users = User.query.filter(User.username.in_([item['username'] for item in normalized])).all()
        users_by_username = {user.username: user for user in users}

        for item in normalized:
            username = item['username']
            user = users_by_username.get(username)
            if not user:
                raise ValueError(f'Usuário responsável não encontrado: {username}.')
            if not self._is_user_eligible_as_event_responsible(user):
                raise ValueError(f'Usuário sem permissão para ser responsável pelo evento: {username}.')

        return normalized

    def _sync_event_responsibles(self, event, responsibles_data):
        if not event:
            return

        event.responsibles.clear()
        db.session.flush()

        primary_username = None
        for item in responsibles_data:
            event.responsibles.append(EventResponsible(
                user_username=item['username'],
                is_primary=bool(item.get('is_primary')),
            ))
            if item.get('is_primary'):
                primary_username = item['username']

        event.owner_username = primary_username
        db.session.flush()

    @staticmethod
    def is_event_responsible(user, event):
        if not user or not event:
            return False
        username = getattr(user, 'username', None)
        if not username:
            return False
        for responsible in getattr(event, 'responsibles', []) or []:
            if responsible.user_username == username:
                return True
        return bool(event.owner_username and event.owner_username == username)
```

- [ ] **Step 5: Wire helpers into create and update**

In `create_event`, after `self.event_repo.save(event)`, add:

```python
        responsibles = self._normalize_event_responsibles_payload(
            data.get('responsaveis'),
            default_primary_username=owner_username,
        )
        self._sync_event_responsibles(event, responsibles)
```

In `create_event`, before the notification call, persist pending relationship changes:

```python
        db.session.commit()
```

The end of `create_event` should call the notification after the commit:

```python
        db.session.commit()
        self._notify_owner_event_created(event)

        return event
```

In `update_event`, after registration categories are resolved and before `_sync_event_allowed_roles`, add:

```python
        if 'responsaveis' in data:
            responsibles = self._normalize_event_responsibles_payload(
                data.get('responsaveis'),
                default_primary_username=event.owner_username,
            )
            self._sync_event_responsibles(event, responsibles)
        elif not getattr(event, 'responsibles', None):
            responsibles = self._normalize_event_responsibles_payload(
                None,
                default_primary_username=event.owner_username,
            )
            self._sync_event_responsibles(event, responsibles)
```

- [ ] **Step 6: Run the service tests**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_event_responsibles.py -q
```

Expected: PASS for the Task 1 and Task 2 tests.

- [ ] **Step 7: Commit Task 2**

```powershell
git add app/services/event_service.py tests/test_event_responsibles.py
git commit -m "feat: sync event responsibles in service"
```

---

### Task 3: Permissions, Listings, Repository, And Dashboard Filters

**Files:**
- Modify: `tests/test_event_responsibles.py`
- Modify: `tests/test_api.py`
- Modify: `app/services/event_service.py`
- Modify: `app/repositories/event_repository.py`
- Modify: `app/api/events.py`

- [ ] **Step 1: Add failing permission and listing tests**

Append these tests to `tests/test_event_responsibles.py`:

```python
def test_co_responsible_has_same_management_permissions_as_primary(app, admin_user):
    owner = db.session.get(User, admin_user.username)
    co_responsible = _persist_user(
        'permission_co_resp',
        role='professor',
        cpf='90000000006',
        can_create_events=True,
    )
    outsider = _persist_user(
        'permission_outsider',
        role='professor',
        cpf='90000000007',
        can_create_events=True,
    )
    event = EventService().create_event(owner.username, _event_payload(
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': co_responsible.username, 'is_primary': False},
        ]
    ))

    assert EventService.can_manage_event(owner, event) is True
    assert EventService.can_manage_event(co_responsible, event) is True
    assert EventService.can_manage_event_participants(co_responsible, event) is True
    assert EventService.can_add_event_participants(co_responsible, event) is True
    assert EventService.can_notify_event_participants(co_responsible, event) is True
    assert EventService.can_manage_event_certificates(co_responsible, event) is True
    assert EventService.can_delete_event(co_responsible, event) is True
    assert EventService.can_manage_event(outsider, event) is False


def test_list_events_for_creator_includes_co_responsible_events(app, admin_user):
    owner = db.session.get(User, admin_user.username)
    co_responsible = _persist_user(
        'listing_co_resp',
        role='professor',
        cpf='90000000008',
        can_create_events=True,
    )
    other = _persist_user(
        'listing_other_resp',
        role='professor',
        cpf='90000000009',
        can_create_events=True,
    )
    visible_event = EventService().create_event(owner.username, _event_payload(
        nome='Evento Visivel ao Co Responsavel',
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': co_responsible.username, 'is_primary': False},
        ]
    ))
    EventService().create_event(owner.username, _event_payload(
        nome='Evento Fora do Co Responsavel',
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': other.username, 'is_primary': False},
        ]
    ))

    pagination = EventService().list_events_paginated(co_responsible, page=1, per_page=10)
    event_ids = {event.id for event in pagination.items}

    assert visible_event.id in event_ids
    assert len(event_ids) == 1


def test_owner_filter_matches_primary_and_co_responsible(app, admin_user):
    owner = db.session.get(User, admin_user.username)
    co_responsible = _persist_user(
        'filter_co_resp',
        role='professor',
        cpf='90000000010',
        can_create_events=True,
        nome='Filtro Co Responsavel',
    )
    event = EventService().create_event(owner.username, _event_payload(
        nome='Evento Filtrado Por Co Responsavel',
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': co_responsible.username, 'is_primary': False},
        ]
    ))

    pagination = EventService().list_events_paginated(
        owner,
        page=1,
        per_page=10,
        filters={'owner': 'Filtro Co'},
    )

    assert [item.id for item in pagination.items] == [event.id]
```

Append this API test to `tests/test_api.py`:

```python
def test_dashboard_owner_filter_accepts_event_co_responsible(client, app):
    with app.app_context():
        admin = db.session.get(User, 'admin_test')
        co_responsible = User(
            username='dashboard_co_resp_filter',
            role='professor',
            nome='Dashboard Co Responsavel',
            cpf='91000000001',
            can_create_events=True,
        )
        co_responsible.set_password('1234')
        db.session.add(co_responsible)
        db.session.flush()

        event = EventService().create_event(admin.username, {
            'nome': 'Evento Dashboard Co Responsavel',
            'descricao': 'Desc',
            'is_rapido': True,
            'carga_horaria_rapida': 2,
            'data_inicio': date.today().isoformat(),
            'hora_inicio': '10:00',
            'data_fim': date.today().isoformat(),
            'hora_fim': '12:00',
            'responsaveis': [
                {'username': admin.username, 'is_primary': True},
                {'username': co_responsible.username, 'is_primary': False},
            ],
        })
        event_id = event.id

    _login_admin(client)
    response = client.get('/api/dashboard/analytics?period_days=3650&owner_username=dashboard_co_resp_filter')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['summary']['total_events'] == 1
    assert any(option['username'] == 'dashboard_co_resp_filter' for option in payload['filter_options']['owners'])
    assert event_id is not None
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_event_responsibles.py::test_co_responsible_has_same_management_permissions_as_primary tests/test_event_responsibles.py::test_list_events_for_creator_includes_co_responsible_events tests/test_event_responsibles.py::test_owner_filter_matches_primary_and_co_responsible tests/test_api.py::test_dashboard_owner_filter_accepts_event_co_responsible -q
```

Expected: FAIL because permissions, list filters and dashboard still consult `owner_username` directly.

- [ ] **Step 3: Update event permissions in the service**

In `app/services/event_service.py`, replace `is_event_owner` with:

```python
    @staticmethod
    def is_event_owner(user, event):
        return EventService.is_event_responsible(user, event)
```

In `can_view_event`, replace the branch for creators with:

```python
        if EventService.can_create_events(user):
            return EventService.is_event_responsible(user, event)
```

In `can_edit_event`, keep the admin and coordinator branches and replace the final return with:

```python
        return EventService.is_event_responsible(user, event) and EventService._can_manage_own_events(user)
```

In `can_delete_event`, keep the admin and coordinator branches and replace the final return with:

```python
        return EventService.is_event_responsible(user, event) and EventService._can_manage_own_events(user)
```

- [ ] **Step 4: Update service list queries**

In `app/services/event_service.py`, ensure `EventResponsible` is imported from `app.models`.

In `get_events_for_user_paginated`, replace this creator branch:

```python
        elif self.can_create_events(user):
            query = query.filter_by(owner_username=user.username)
```

with:

```python
        elif self.can_create_events(user):
            query = query.filter(
                Event.responsibles.any(EventResponsible.user_username == user.username)
            )
```

In `list_events_paginated`, replace this creator branch:

```python
        elif self.can_create_events(user):
            query = query.filter(Event.owner_username == user.username)
```

with:

```python
        elif self.can_create_events(user):
            query = query.filter(
                Event.responsibles.any(EventResponsible.user_username == user.username)
            )
```

In the `filters.get('owner')` branch of `list_events_paginated`, replace the existing `owner_username` filter with:

```python
            if filters.get('owner'):
                owner_search = f"%{filters['owner']}%"
                query = (
                    query
                    .join(EventResponsible, EventResponsible.event_id == Event.id)
                    .outerjoin(User, User.username == EventResponsible.user_username)
                    .filter(or_(
                        EventResponsible.user_username.ilike(owner_search),
                        User.nome.ilike(owner_search),
                    ))
                    .distinct()
                )
```

- [ ] **Step 5: Update repository owner lookup**

In `app/repositories/event_repository.py`, replace the file with:

```python
from app.models import Event, EventResponsible
from .base_repository import BaseRepository
from typing import List, Optional


class EventRepository(BaseRepository[Event]):
    """
    Repository for Event entity operations.
    """
    def __init__(self):
        super().__init__(Event)

    def get_by_owner(self, owner_username: str) -> List[Event]:
        """Retrieves all events where the user is primary or co-responsible."""
        return (
            Event.query
            .filter(Event.responsibles.any(EventResponsible.user_username == owner_username))
            .all()
        )

    def get_by_token(self, token: str) -> Optional[Event]:
        """
        Retrieves an event by its public token.

        Args:
            token (str): The public token.

        Returns:
            Event: The event object or None.
        """
        return self.find_one_by(token_publico=token)
```

- [ ] **Step 6: Update API visibility and dashboard owner filtering**

In `app/api/events.py`, add `EventResponsible` to the model imports.

In `_apply_event_visibility_scope`, replace the professor branch with:

```python
    if current_user.role == 'professor':
        query = query.filter(
            Event.responsibles.any(EventResponsible.user_username == current_user.username)
        )
```

In `dashboard_analytics`, replace:

```python
    if owner_username:
        scoped_events_query = scoped_events_query.filter(Event.owner_username == owner_username)
```

with:

```python
    if owner_username:
        scoped_events_query = scoped_events_query.filter(
            Event.responsibles.any(EventResponsible.user_username == owner_username)
        )
```

Replace the current `owner_rows` query with:

```python
    owner_event_ids = [
        event_id
        for (event_id,) in owner_options_query.with_entities(Event.id).all()
    ]
    owner_rows = []
    if owner_event_ids:
        owner_rows = (
            db.session.query(EventResponsible.user_username, User.nome)
            .select_from(EventResponsible)
            .outerjoin(User, User.username == EventResponsible.user_username)
            .filter(EventResponsible.event_id.in_(owner_event_ids))
            .group_by(EventResponsible.user_username, User.nome)
            .order_by(func.lower(func.coalesce(User.nome, EventResponsible.user_username)).asc())
            .all()
        )
```

Keep the existing `owner_options = [...]` list comprehension, using `username` and `name` from the new query.

- [ ] **Step 7: Run permission, listing and dashboard tests**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_event_responsibles.py tests/test_api.py::test_dashboard_owner_filter_accepts_event_co_responsible -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

```powershell
git add app/services/event_service.py app/repositories/event_repository.py app/api/events.py tests/test_event_responsibles.py tests/test_api.py
git commit -m "feat: authorize event co-responsibles"
```

---

### Task 4: Serialization And Lifecycle Notifications

**Files:**
- Modify: `tests/test_event_responsibles.py`
- Modify: `app/serializers.py`
- Modify: `app/services/event_service.py`

- [ ] **Step 1: Add failing serialization and notification tests**

Append these tests to `tests/test_event_responsibles.py`:

```python
def test_serialize_event_returns_primary_and_all_responsibles(app, admin_user):
    owner = db.session.get(User, admin_user.username)
    co_responsible = _persist_user(
        'serialize_co_resp',
        role='gestor',
        cpf='90000000011',
        nome='Serializar Co Responsavel',
    )
    event = EventService().create_event(owner.username, _event_payload(
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': co_responsible.username, 'is_primary': False},
        ]
    ))

    payload = serialize_event(event, owner)

    assert payload['owner'] == owner.username
    assert payload['owner_name'] == owner.nome
    assert payload['responsavel_principal']['username'] == owner.username
    assert payload['responsaveis'] == [
        {
            'username': owner.username,
            'nome': owner.nome,
            'email': owner.email,
            'role': owner.role,
            'is_primary': True,
        },
        {
            'username': 'serialize_co_resp',
            'nome': 'Serializar Co Responsavel',
            'email': None,
            'role': 'gestor',
            'is_primary': False,
        },
    ]


def test_event_lifecycle_notifications_are_sent_to_all_responsibles(app, admin_user, monkeypatch):
    owner = db.session.get(User, admin_user.username)
    owner.email = 'owner.lifecycle@test.local'
    co_responsible = _persist_user(
        'notify_co_resp',
        role='gestor',
        cpf='90000000012',
        email='co.lifecycle@test.local',
    )
    sent = []

    service = EventService()
    monkeypatch.setattr(service.notification_service, 'send_email_task', lambda **kwargs: sent.append(kwargs))

    service.create_event(owner.username, _event_payload(
        responsaveis=[
            {'username': owner.username, 'is_primary': True},
            {'username': co_responsible.username, 'is_primary': False},
        ]
    ))

    assert {item['to_email'] for item in sent} == {
        'owner.lifecycle@test.local',
        'co.lifecycle@test.local',
    }
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_event_responsibles.py::test_serialize_event_returns_primary_and_all_responsibles tests/test_event_responsibles.py::test_event_lifecycle_notifications_are_sent_to_all_responsibles -q
```

Expected: FAIL because `serialize_event()` does not return `responsaveis`, and lifecycle notifications still use only `owner_username`.

- [ ] **Step 3: Add responsible serialization helper**

In `app/serializers.py`, add this helper after `serialize_user`:

```python
def serialize_event_responsibles(event):
    """Serializes event responsibles with primary first and legacy fallback."""
    responsibles = []

    for responsible in getattr(event, 'responsibles', []) or []:
        user = responsible.user
        responsibles.append({
            'username': responsible.user_username,
            'nome': user.nome if user else responsible.user_username,
            'email': user.email if user else None,
            'role': user.role if user else None,
            'is_primary': bool(responsible.is_primary),
        })

    if not responsibles and getattr(event, 'owner_username', None):
        from app.models import User

        owner_user = User.query.filter_by(username=event.owner_username).first()
        responsibles.append({
            'username': event.owner_username,
            'nome': owner_user.nome if owner_user else event.owner_username,
            'email': owner_user.email if owner_user else None,
            'role': owner_user.role if owner_user else None,
            'is_primary': True,
        })

    return sorted(
        responsibles,
        key=lambda item: (not item['is_primary'], str(item.get('nome') or item['username']).lower()),
    )
```

- [ ] **Step 4: Derive owner fields from the primary responsible**

In `serialize_event`, replace the current `owner_user` and `owner_name` lines with:

```python
    responsibles_payload = serialize_event_responsibles(event)
    primary_responsible = next(
        (item for item in responsibles_payload if item.get('is_primary')),
        responsibles_payload[0] if responsibles_payload else None,
    )
    owner_username = primary_responsible['username'] if primary_responsible else event.owner_username
    owner_name = (
        primary_responsible['nome']
        if primary_responsible and primary_responsible.get('nome')
        else (event.owner_username or 'Sistema')
    )
```

In the returned dictionary, replace the owner fields and add the new fields:

```python
        'owner': owner_username,
        'owner_name': owner_name,
        'responsavel_principal': primary_responsible,
        'responsaveis': responsibles_payload,
```

- [ ] **Step 5: Send lifecycle notifications to all responsibles**

In `app/services/event_service.py`, add this helper before `_notify_owner_event_created`:

```python
    def _get_event_responsible_users(self, event):
        users = []
        seen = set()

        for responsible in getattr(event, 'responsibles', []) or []:
            user = responsible.user
            if user and user.username not in seen:
                users.append(user)
                seen.add(user.username)

        if not users and getattr(event, 'owner_username', None):
            owner = User.query.filter_by(username=event.owner_username).first()
            if owner:
                users.append(owner)

        return users
```

Replace `_notify_owner_event_created` with:

```python
    def _notify_owner_event_created(self, event):
        """Sends an email confirmation to all event responsibles when an event is created."""
        responsible_users = [user for user in self._get_event_responsible_users(event) if user.email]
        if not responsible_users:
            return

        app_url = (current_app.config.get('BASE_URL') or '').rstrip('/')
        event_link = f"{app_url}/inscrever/{event.token_publico}" if app_url else f"/inscrever/{event.token_publico}"
        manage_link = f"{app_url}/eventos_admin" if app_url else '/eventos_admin'
        event_date = event.data_inicio.strftime('%d/%m/%Y') if event.data_inicio else '-'
        event_time = event.hora_inicio.strftime('%H:%M') if event.hora_inicio else '-'

        for responsible_user in responsible_users:
            self.notification_service.send_email_task(
                to_email=responsible_user.email,
                subject=f"Evento criado: {event.nome}",
                template_name='event_created_owner.html',
                template_data={
                    'user_name': responsible_user.nome or responsible_user.username,
                    'event_name': event.nome,
                    'event_type': event.tipo,
                    'event_date': event_date,
                    'event_time': event_time,
                    'event_status': event.status,
                    'event_link': event_link,
                    'manage_link': manage_link,
                    'year': datetime.now().year,
                },
            )
```

Apply the same `responsible_users` loop shape to `_notify_owner_event_updated`.

For deletion, capture users before deleting. In `delete_event`, add before `self.event_repo.delete(event)`:

```python
        event_responsible_users = self._get_event_responsible_users(event)
```

Replace the delete notification call with:

```python
        self._notify_owner_event_deleted(event_responsible_users, event_name, event_type, event_date, event_time)
```

Replace `_notify_owner_event_deleted` with:

```python
    def _notify_owner_event_deleted(self, responsible_users, event_name, event_type, event_date, event_time):
        """Sends an email confirmation to all event responsibles when an event is deleted."""
        recipients = [user for user in responsible_users if user and user.email]
        if not recipients:
            return

        app_url = (current_app.config.get('BASE_URL') or '').rstrip('/')
        manage_link = f"{app_url}/eventos_admin" if app_url else '/eventos_admin'

        for responsible_user in recipients:
            self.notification_service.send_email_task(
                to_email=responsible_user.email,
                subject=f"Evento excluído: {event_name}",
                template_name='event_deleted_owner.html',
                template_data={
                    'user_name': responsible_user.nome or responsible_user.username,
                    'event_name': event_name,
                    'event_type': event_type,
                    'event_date': event_date,
                    'event_time': event_time,
                    'manage_link': manage_link,
                    'changed_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
                    'year': datetime.now().year,
                },
            )
```

- [ ] **Step 6: Run serialization and notification tests**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_event_responsibles.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```powershell
git add app/serializers.py app/services/event_service.py tests/test_event_responsibles.py
git commit -m "feat: serialize and notify event responsibles"
```

---

### Task 5: API Options And User Interface

**Files:**
- Modify: `tests/test_api.py`
- Modify: `app/api/events.py`
- Modify: `app/main/routes.py`
- Create: `app/templates/partials/event_responsibles_editor.html`
- Modify: `app/templates/event_create.html`
- Modify: `app/templates/event_edit.html`
- Modify: `app/templates/events_admin.html`

- [ ] **Step 1: Add failing API option test**

Append this test to `tests/test_api.py`:

```python
def test_event_responsible_options_returns_only_management_eligible_users(client, app):
    with app.app_context():
        creator = User(
            username='responsible_options_creator',
            role='professor',
            nome='Responsavel Options Creator',
            cpf='91000000002',
            can_create_events=True,
        )
        creator.set_password('1234')
        eligible = User(
            username='responsible_options_eligible',
            role='gestor',
            nome='Responsavel Options Eligible',
            cpf='91000000003',
        )
        eligible.set_password('1234')
        participant = User(
            username='responsible_options_participant',
            role='participante',
            nome='Responsavel Options Participant',
            cpf='91000000004',
        )
        participant.set_password('1234')
        db.session.add_all([creator, eligible, participant])
        db.session.commit()

    _login_user(client, 'responsible_options_creator')
    response = client.get('/api/event_responsibles/options?q=Responsavel Options')

    assert response.status_code == 200
    usernames = {item['username'] for item in response.get_json()}
    assert 'responsible_options_eligible' in usernames
    assert 'responsible_options_creator' in usernames
    assert 'responsible_options_participant' not in usernames
```

- [ ] **Step 2: Run the API option test and verify it fails**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_event_responsible_options_returns_only_management_eligible_users -q
```

Expected: FAIL with `404` because the endpoint does not exist.

- [ ] **Step 3: Add the responsible options endpoint**

In `app/api/events.py`, add this route after `listar_eventos_admin`:

```python
@bp.route('/event_responsibles/options', methods=['GET'])
@login_required
def listar_event_responsaveis_opcoes():
    """Search users eligible to be linked as event responsibles."""
    if not EventService.can_access_event_management(current_user):
        return jsonify([]), 403

    query_text = (request.args.get('q') or '').strip()
    include_username = (request.args.get('include_username') or '').strip()

    query = User.query.filter(or_(
        User.role.in_(['admin', 'coordenador', 'gestor', 'extensao']),
        User.can_create_events.is_(True),
    ))

    if query_text:
        search = f'%{query_text}%'
        query = query.filter(or_(
            User.username.ilike(search),
            User.nome.ilike(search),
            User.email.ilike(search),
        ))
    elif include_username:
        query = query.filter(User.username == include_username)
    else:
        query = query.order_by(User.nome.asc()).limit(20)

    users = query.order_by(User.nome.asc(), User.username.asc()).limit(20).all()
    if include_username and all(user.username != include_username for user in users):
        included_user = User.query.filter_by(username=include_username).first()
        if included_user and EventService.can_access_event_management(included_user):
            users.insert(0, included_user)

    return jsonify([serialize_user(user) for user in users])
```

Also add `serialize_user` to the imports from `app.serializers`:

```python
from app.serializers import serialize_event, serialize_user
```

- [ ] **Step 4: Pass initial responsible payloads to create and edit routes**

In `app/main/routes.py`, update imports inside `criar_evento_page` and `editar_evento_page` by adding `serialize_event` and `serialize_user` from `app.serializers`.

Replace `criar_evento_page` with:

```python
@bp.route('/criar_evento')
@login_required
def criar_evento_page():
    """Dedicated page for creating new events with multiple activities."""
    if not EventService.can_create_events(current_user):
        return "Acesso negado", 403

    current_user_payload = serialize_user(current_user)
    current_user_payload['is_primary'] = True
    return render_template(
        'event_create.html',
        user=current_user,
        initial_event_responsibles=[current_user_payload],
    )
```

Replace the final `render_template` in `editar_evento_page` with:

```python
    event_payload = serialize_event(event, current_user)
    return render_template(
        'event_edit.html',
        user=current_user,
        event=event,
        event_payload=event_payload,
        initial_event_responsibles=event_payload.get('responsaveis', []),
    )
```

- [ ] **Step 5: Create the shared responsible editor partial**

Create `app/templates/partials/event_responsibles_editor.html`:

```html
<div class="mb-4 event-responsibles-editor">
    <label class="form-label fw-bold text-slate-700">Responsaveis pelo Evento</label>
    <div class="rounded-4 border bg-slate-50 p-3">
        <div class="input-group input-group-sm mb-3">
            <span class="input-group-text bg-white"><i class="fa-solid fa-user-magnifying-glass"></i></span>
            <input type="search" class="form-control" id="eventResponsibleSearch" placeholder="Buscar por nome, usuario ou e-mail" autocomplete="off">
            <button type="button" class="btn btn-outline-primary" onclick="searchEventResponsibles()">
                <i class="fa-solid fa-magnifying-glass me-1"></i>Buscar
            </button>
        </div>
        <div id="eventResponsibleSearchResults" class="d-grid gap-2 mb-3"></div>
        <div id="eventResponsiblesList" class="d-grid gap-2"></div>
    </div>
    <small class="text-muted">O principal aparece como referencia visual; todos os vinculados podem gerenciar o evento.</small>
</div>

<script type="application/json" id="initialEventResponsiblesJson">{{ initial_event_responsibles|default([])|tojson }}</script>
<script>
    let selectedEventResponsibles = [];

    function escapeResponsibleHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function normalizeResponsibleOption(user, isPrimary = false) {
        return {
            username: String(user.username || '').trim(),
            nome: user.nome || user.username || '',
            email: user.email || '',
            role: user.role || '',
            is_primary: Boolean(isPrimary || user.is_primary),
        };
    }

    function ensureSinglePrimaryResponsible() {
        if (!selectedEventResponsibles.length) return;
        const primaryIndex = selectedEventResponsibles.findIndex((item) => item.is_primary);
        if (primaryIndex === -1) {
            selectedEventResponsibles[0].is_primary = true;
            return;
        }
        selectedEventResponsibles = selectedEventResponsibles.map((item, index) => ({
            ...item,
            is_primary: index === primaryIndex,
        }));
    }

    function renderEventResponsibles() {
        ensureSinglePrimaryResponsible();
        const container = document.getElementById('eventResponsiblesList');
        if (!container) return;

        if (!selectedEventResponsibles.length) {
            container.innerHTML = '<div class="text-muted small">Nenhum responsavel selecionado.</div>';
            return;
        }

        container.innerHTML = selectedEventResponsibles.map((item) => `
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 rounded-3 border bg-white p-2" data-username="${escapeResponsibleHtml(item.username)}">
                <div>
                    <div class="fw-semibold small">${escapeResponsibleHtml(item.nome || item.username)}</div>
                    <div class="text-muted x-small">${escapeResponsibleHtml(item.username)}${item.email ? ' · ' + escapeResponsibleHtml(item.email) : ''}</div>
                </div>
                <div class="d-flex align-items-center gap-2">
                    <button type="button" class="btn btn-sm ${item.is_primary ? 'btn-primary' : 'btn-light border'}" onclick="setPrimaryResponsible('${escapeResponsibleHtml(item.username)}')">
                        <i class="fa-solid fa-star me-1"></i>${item.is_primary ? 'Principal' : 'Marcar principal'}
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeEventResponsible('${escapeResponsibleHtml(item.username)}')" ${selectedEventResponsibles.length === 1 ? 'disabled' : ''}>
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }

    function addEventResponsible(user) {
        const normalized = normalizeResponsibleOption(user, selectedEventResponsibles.length === 0);
        if (!normalized.username) return;
        if (selectedEventResponsibles.some((item) => item.username === normalized.username)) return;
        selectedEventResponsibles.push(normalized);
        renderEventResponsibles();
    }

    function removeEventResponsible(username) {
        selectedEventResponsibles = selectedEventResponsibles.filter((item) => item.username !== username);
        renderEventResponsibles();
    }

    function setPrimaryResponsible(username) {
        selectedEventResponsibles = selectedEventResponsibles.map((item) => ({
            ...item,
            is_primary: item.username === username,
        }));
        renderEventResponsibles();
    }

    function collectEventResponsibles() {
        ensureSinglePrimaryResponsible();
        return selectedEventResponsibles.map((item) => ({
            username: item.username,
            is_primary: Boolean(item.is_primary),
        }));
    }

    async function searchEventResponsibles() {
        const input = document.getElementById('eventResponsibleSearch');
        const results = document.getElementById('eventResponsibleSearchResults');
        const term = (input?.value || '').trim();
        if (!results) return;
        if (term.length < 2) {
            results.innerHTML = '<div class="text-muted x-small">Digite pelo menos 2 caracteres.</div>';
            return;
        }

        results.innerHTML = '<div class="text-muted x-small">Buscando...</div>';
        const response = await fetch(apiUrl(`/api/event_responsibles/options?q=${encodeURIComponent(term)}`));
        const users = response.ok ? await response.json() : [];
        const availableUsers = users.filter((user) => !selectedEventResponsibles.some((item) => item.username === user.username));

        if (!availableUsers.length) {
            results.innerHTML = '<div class="text-muted x-small">Nenhum responsavel elegivel encontrado.</div>';
            return;
        }

        results.innerHTML = availableUsers.map((user) => `
            <button type="button" class="btn btn-sm btn-light border text-start" onclick='addEventResponsible(${JSON.stringify(user)})'>
                <span class="fw-semibold">${escapeResponsibleHtml(user.nome || user.username)}</span>
                <span class="text-muted x-small ms-1">${escapeResponsibleHtml(user.username)}</span>
            </button>
        `).join('');
    }

    document.addEventListener('DOMContentLoaded', () => {
        const jsonElement = document.getElementById('initialEventResponsiblesJson');
        try {
            selectedEventResponsibles = JSON.parse(jsonElement?.textContent || '[]')
                .map((item) => normalizeResponsibleOption(item, item.is_primary))
                .filter((item) => item.username);
        } catch (error) {
            selectedEventResponsibles = [];
        }
        renderEventResponsibles();
    });
</script>
```

- [ ] **Step 6: Include the partial and send responsibles from create/edit**

In `app/templates/event_create.html`, add this include immediately after the event description block:

```html
                        {% include 'partials/event_responsibles_editor.html' %}
```

In the submit handler, after `const registrationSettings = collectRegistrationSettings();`, add:

```javascript
        const eventResponsibles = collectEventResponsibles();
        if (!eventResponsibles.length) {
            Swal.fire('Validação', 'Selecione ao menos um responsável pelo evento.', 'warning');
            return;
        }
        if (eventResponsibles.filter((item) => item.is_primary).length !== 1) {
            Swal.fire('Validação', 'Selecione exatamente um responsável principal.', 'warning');
            return;
        }
```

In the `data` object, add:

```javascript
            responsaveis: eventResponsibles,
```

Make the same three changes in `app/templates/event_edit.html`.

- [ ] **Step 7: Show all responsibles in the admin list**

In `app/templates/events_admin.html`, before the `tbody.innerHTML +=` block in `carregarEventos`, add:

```javascript
            const responsibles = Array.isArray(ev.responsaveis) ? ev.responsaveis : [];
            const primaryResponsible = ev.responsavel_principal || responsibles.find((item) => item.is_primary) || null;
            const coResponsibles = responsibles.filter((item) => !item.is_primary);
            const responsibleLabel = primaryResponsible
                ? `${escapeHtml(primaryResponsible.nome || primaryResponsible.username)}${coResponsibles.length ? ` +${coResponsibles.length}` : ''}`
                : escapeHtml(ev.owner_name || ev.owner || 'Sistema');
            const responsibleTitle = responsibles.length
                ? responsibles.map((item) => `${item.is_primary ? 'Principal: ' : 'Co-responsavel: '}${item.nome || item.username}`).join('\n')
                : (ev.owner_name || ev.owner || 'Sistema');
```

Replace the responsible cell with:

```javascript
                    <td data-label="Responsável"><span class="badge bg-light text-dark border" title="${escapeHtml(responsibleTitle)}">${responsibleLabel}</span></td>
```

- [ ] **Step 8: Run API and template-adjacent tests**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_event_responsible_options_returns_only_management_eligible_users tests/test_event_responsibles.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit Task 5**

```powershell
git add app/api/events.py app/main/routes.py app/templates/partials/event_responsibles_editor.html app/templates/event_create.html app/templates/event_edit.html app/templates/events_admin.html tests/test_api.py
git commit -m "feat: add event responsible selector"
```

---

### Task 6: Full Verification

**Files:**
- No code files changed in this task.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_event_responsibles.py tests/test_api.py tests/test_services.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the full test suite**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest -q
```

Expected: PASS.

- [ ] **Step 3: Validate database migration on the configured environment**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m flask db upgrade
```

Expected: migration completes and the database contains `event_responsibles` rows copied from existing `events.owner_username` values.

- [ ] **Step 4: Start the Flask app**

Run:

```powershell
d:\Unieuro\UniEventos\.venv\Scripts\python.exe run.py
```

Expected: app starts at `http://localhost:5000`.

- [ ] **Step 5: Manual browser validation**

Open `http://localhost:5000`, sign in with a management-eligible user, and validate these flows:

1. Create an event with the current user as primary and one co-responsible.
2. Edit the event as the co-responsible.
3. Change the primary responsible and save.
4. Confirm the event list shows the primary and `+1` for co-responsible.
5. Confirm the old owner display still works through `owner` and `owner_name` in API responses.

- [ ] **Step 6: Commit final verification note if a test-only adjustment was needed**

Only run this commit if Task 6 required a small test correction:

```powershell
git add tests/test_event_responsibles.py tests/test_api.py tests/test_services.py
git commit -m "test: cover event co-responsibles"
```

---

## Self-Review

**Spec coverage:**
- Multiple responsaveis with exactly one primary: Tasks 1 and 2.
- Same permissions for principal and co-responsaveis: Task 3.
- UI shows all responsaveis: Task 5.
- `owner_username` compatibility mirror: Tasks 1, 2 and 4.
- Migration from legacy events: Task 1.
- Notifications to all responsaveis: Task 4.
- Filters by any responsible: Task 3.

**Type consistency:**
- Backend payload key: `responsaveis`.
- Model relationship: `Event.responsibles`.
- Relation model: `EventResponsible` with `event_id`, `user_username`, `is_primary`, `created_at`.
- Serializer keys: `responsavel_principal`, `responsaveis`, `owner`, `owner_name`.

**Verification commands:**
- `d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest tests/test_event_responsibles.py tests/test_api.py tests/test_services.py -q`
- `d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m pytest -q`
- `d:\Unieuro\UniEventos\.venv\Scripts\python.exe -m flask db upgrade`