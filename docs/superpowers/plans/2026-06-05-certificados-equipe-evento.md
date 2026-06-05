# Certificados da Equipe do Evento Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build event-scoped team certificates for speakers, facilitators, responsibles, and event staff, with separate design, recipients, PDF generation, validation, preview/download, and email delivery.

**Architecture:** Add event-level team certificate configuration plus a dedicated recipient table. Reuse `CertificateService` for PDF rendering and fixed validation elements, but keep team templates, endpoints, and delivery state separate from participant and institutional certificates. Add a focused `EventTeamCertificateService` to synchronize automatic recipients, generate PDFs, and queue team certificate emails.

**Tech Stack:** Flask, Flask-Login, SQLAlchemy, Flask-Migrate/Alembic, Jinja, Bootstrap, ReportLab via existing `CertificateService`, pytest.

---

**Commit Policy:** Do not run `git commit` during execution unless the user explicitly asks. Replace commit steps with `git diff --check`, focused tests, and a working-tree status checkpoint.

## File Structure

- Modify `app/models.py`: add `Event.cert_team_bg_path`, `Event.cert_team_template_json`, `Event.team_certificate_recipients`, and `EventTeamCertificateRecipient`.
- Add `migrations/versions/7b2e1d4c9a0f_add_event_team_certificates.py`: Alembic migration for the new event fields and table.
- Add `app/services/event_team_certificate_service.py`: sync automatic recipients, normalize recipient payloads, build default team template, generate PDFs, queue emails.
- Modify `app/services/certificate_service.py`: allow designer mode `team_event` to normalize as event-style mode with `{{NOME}}` fixed element.
- Modify `app/api/certificates.py`: add team certificate endpoints and batch job state.
- Modify `app/main/routes.py`: add pages `/certificados_equipe/<event_id>` and `/designer_certificado_equipe/<event_id>`, and include team validation in `/validar/<hash>`.
- Modify `app/templates/certificate_designer.html`: add `team_event` mode with separate URLs, labels, default text, variables, and batch text.
- Add `app/templates/team_certificate_delivery.html`: management UI for team recipients and deliveries.
- Add `app/templates/emails/team_certificate_ready.html`: email for team certificates.
- Modify `app/templates/validation.html`: display team certificate type, role, activity, and hours.
- Modify `app/templates/certificate_delivery.html`: add a visible path to team certificates without changing the existing participant certificate table behavior.
- Modify `tests/test_models.py`, `tests/test_services.py`, and `tests/test_api.py`: model, service, API, permission, PDF, email, UI, and validation coverage.

## Task 1: Data Model And Migration

**Files:**
- Modify: `app/models.py`
- Add: `migrations/versions/7b2e1d4c9a0f_add_event_team_certificates.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing model test**

Add this import and test to `tests/test_models.py`:

```python
from datetime import date, time

from app.extensions import db
from app.models import Activity, Event, EventTeamCertificateRecipient, User


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

        saved = EventTeamCertificateRecipient.query.one()
        assert saved.event.nome == 'Evento Equipe'
        assert saved.activity.nome == 'Oficina de Extensao'
        assert saved.cpf == '12345678901'
        assert event.team_certificate_recipients[0].role_label == 'Facilitador'
        assert event.cert_team_bg_path == 'file/fundo_padrao.png'
```

- [ ] **Step 2: Run the failing model test**

Run: `python -m pytest tests/test_models.py::test_event_team_certificate_recipient_relationship -q`

Expected: FAIL with `ImportError` or `NameError` for `EventTeamCertificateRecipient`.

- [ ] **Step 3: Implement model fields and table**

In `app/models.py`, add these fields after `Event.cert_template_json`:

```python
    cert_team_bg_path = db.Column(db.String(200), nullable=True, default='file/fundo_padrao.png')
    cert_team_template_json = db.Column(db.Text, nullable=True)
```

Add this relationship after `Event.responsibles`:

```python
    team_certificate_recipients = db.relationship(
        'EventTeamCertificateRecipient',
        back_populates='event',
        cascade='all, delete-orphan',
        order_by=lambda: (
            EventTeamCertificateRecipient.role_label,
            EventTeamCertificateRecipient.nome,
            EventTeamCertificateRecipient.id,
        ),
    )
```

Add this model after `EventResponsible`:

```python
class EventTeamCertificateRecipient(db.Model):
    """Recipient for event-scoped team certificates."""
    __tablename__ = 'event_team_certificate_recipients'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    cpf = db.Column(CPFDigitsType(), nullable=True)
    role_label = db.Column(db.String(80), nullable=False)
    workload_hours = db.Column(db.String(20), nullable=True)
    source = db.Column(db.String(20), nullable=False, default='manual')
    source_key = db.Column(db.String(160), nullable=True)
    cert_hash = db.Column(db.String(16), unique=True, nullable=True)
    cert_entregue = db.Column(db.Boolean, default=False)
    cert_data_envio = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    event = db.relationship('Event', back_populates='team_certificate_recipients')
    activity = db.relationship('Activity')

    __table_args__ = (
        db.CheckConstraint("source in ('automatico', 'manual')", name='ck_event_team_cert_source'),
        db.UniqueConstraint('event_id', 'source', 'source_key', name='uq_event_team_cert_source_key'),
        db.Index('ix_event_team_cert_event_id', 'event_id'),
        db.Index('ix_event_team_cert_activity_id', 'activity_id'),
        db.Index('ix_event_team_cert_cert_hash', 'cert_hash'),
        db.Index('ix_event_team_cert_entregue', 'cert_entregue'),
        db.Index('ix_event_team_cert_source', 'source'),
    )
```

- [ ] **Step 4: Add migration**

Create `migrations/versions/7b2e1d4c9a0f_add_event_team_certificates.py`:

```python
"""Add event team certificates

Revision ID: 7b2e1d4c9a0f
Revises: a5b7c9d2e4f6
Create Date: 2026-06-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '7b2e1d4c9a0f'
down_revision = 'a5b7c9d2e4f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cert_team_bg_path', sa.String(length=200), nullable=True, server_default='file/fundo_padrao.png'))
        batch_op.add_column(sa.Column('cert_team_template_json', sa.Text(), nullable=True))

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.alter_column('cert_team_bg_path', server_default=None)

    op.create_table(
        'event_team_certificate_recipients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=True),
        sa.Column('nome', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('cpf', sa.String(length=11), nullable=True),
        sa.Column('role_label', sa.String(length=80), nullable=False),
        sa.Column('workload_hours', sa.String(length=20), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('source_key', sa.String(length=160), nullable=True),
        sa.Column('cert_hash', sa.String(length=16), nullable=True),
        sa.Column('cert_entregue', sa.Boolean(), nullable=True),
        sa.Column('cert_data_envio', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source in ('automatico', 'manual')", name='ck_event_team_cert_source'),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id']),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cert_hash'),
        sa.UniqueConstraint('event_id', 'source', 'source_key', name='uq_event_team_cert_source_key'),
    )
    op.create_index('ix_event_team_cert_activity_id', 'event_team_certificate_recipients', ['activity_id'], unique=False)
    op.create_index('ix_event_team_cert_cert_hash', 'event_team_certificate_recipients', ['cert_hash'], unique=False)
    op.create_index('ix_event_team_cert_entregue', 'event_team_certificate_recipients', ['cert_entregue'], unique=False)
    op.create_index('ix_event_team_cert_event_id', 'event_team_certificate_recipients', ['event_id'], unique=False)
    op.create_index('ix_event_team_cert_source', 'event_team_certificate_recipients', ['source'], unique=False)


def downgrade():
    op.drop_index('ix_event_team_cert_source', table_name='event_team_certificate_recipients')
    op.drop_index('ix_event_team_cert_event_id', table_name='event_team_certificate_recipients')
    op.drop_index('ix_event_team_cert_entregue', table_name='event_team_certificate_recipients')
    op.drop_index('ix_event_team_cert_cert_hash', table_name='event_team_certificate_recipients')
    op.drop_index('ix_event_team_cert_activity_id', table_name='event_team_certificate_recipients')
    op.drop_table('event_team_certificate_recipients')

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_column('cert_team_template_json')
        batch_op.drop_column('cert_team_bg_path')
```

- [ ] **Step 5: Run model test**

Run: `python -m pytest tests/test_models.py::test_event_team_certificate_recipient_relationship -q`

Expected: PASS.

- [ ] **Step 6: Checkpoint**

Run: `git diff --check`

Expected: no output.

## Task 2: Team Certificate Service

**Files:**
- Add: `app/services/event_team_certificate_service.py`
- Modify: `app/services/certificate_service.py`
- Test: `tests/test_services.py`

- [ ] **Step 1: Write failing service tests**

Append to `tests/test_services.py`:

```python
def test_event_team_certificate_service_syncs_speakers_and_responsibles_without_duplicates(app, admin_user):
    from datetime import date, time
    from app.models import Activity, ActivitySpeaker, Event, EventResponsible, EventTeamCertificateRecipient, User
    from app.services.event_team_certificate_service import EventTeamCertificateService

    with app.app_context():
        owner = User(username='team_owner', role='professor', nome='Responsavel Evento', cpf='10120230344', email='owner_team@test.local', can_create_events=True)
        owner.set_password('1234')
        helper = User(username='team_helper', role='professor', nome='Apoio Evento', cpf='10120230345', email='helper_team@test.local', can_create_events=True)
        helper.set_password('1234')
        db.session.add_all([owner, helper])
        db.session.flush()

        event = Event(owner_username=owner.username, nome='Evento Equipe Sync', descricao='Teste', tipo='PADRAO', data_inicio=date(2030, 4, 1), hora_inicio=time(9, 0))
        db.session.add(event)
        db.session.flush()

        db.session.add_all([
            EventResponsible(event_id=event.id, user_username=owner.username, is_primary=True),
            EventResponsible(event_id=event.id, user_username=helper.username, is_primary=False),
        ])

        activity = Activity(event_id=event.id, nome='Mesa Redonda', data_atv=date(2030, 4, 2), hora_atv=time(14, 0), carga_horaria=3, vagas=50)
        db.session.add(activity)
        db.session.flush()
        db.session.add_all([
            ActivitySpeaker(activity_id=activity.id, nome='Palestrante Um', email='speaker1@test.local', ordem=0),
            ActivitySpeaker(activity_id=activity.id, nome='Palestrante Dois', email='speaker2@test.local', ordem=1),
        ])
        db.session.commit()

        service = EventTeamCertificateService()
        first = service.sync_event_recipients(event)
        second = service.sync_event_recipients(event)

        recipients = EventTeamCertificateRecipient.query.filter_by(event_id=event.id).order_by(EventTeamCertificateRecipient.source_key).all()
        assert first == {'created': 4, 'updated': 0}
        assert second == {'created': 0, 'updated': 4}
        assert len(recipients) == 4
        assert {item.role_label for item in recipients} == {'Palestrante', 'Responsavel pelo evento', 'Equipe organizadora'}
        assert all(item.source == 'automatico' for item in recipients)
        assert all(item.source_key for item in recipients)


def test_event_team_certificate_service_generates_pdf_with_team_tags(monkeypatch):
    from types import SimpleNamespace
    from app.services.event_team_certificate_service import EventTeamCertificateService

    service = EventTeamCertificateService()
    captured = {}

    def fake_generate_pdf(event, user, activities, total_hours, enrollment=None, template_override=None, tag_overrides=None):
        captured['event'] = event
        captured['user'] = user
        captured['activities'] = activities
        captured['total_hours'] = total_hours
        captured['tag_overrides'] = dict(tag_overrides or {})
        return 'team.pdf'

    monkeypatch.setattr(service.certificate_service, 'generate_pdf', fake_generate_pdf)

    event = SimpleNamespace(id=7, nome='Evento Tags', data_inicio=None, cert_team_bg_path='', cert_team_template_json=None)
    activity = SimpleNamespace(id=3, nome='Oficina Tags', data_atv=None, carga_horaria=6)
    recipient = SimpleNamespace(id=11, nome='Facilitadora Tags', cpf='12345678901', email='facilitadora@test.local', role_label='Facilitador', workload_hours='', cert_hash='TEAMHASH1234567', activity=activity)

    pdf_path = service.generate_recipient_pdf(event, recipient)

    assert pdf_path == 'team.pdf'
    assert captured['event'].designer_mode == 'event'
    assert captured['user'].cpf == 'TEAM-11'
    assert captured['activities'] == [activity]
    assert captured['total_hours'] == '6'
    assert captured['tag_overrides']['{{PAPEL}}'] == 'Facilitador'
    assert captured['tag_overrides']['{{ATIVIDADE}}'] == 'Oficina Tags'
    assert captured['tag_overrides']['{{HORAS}}'] == '6'
    assert captured['tag_overrides']['{{CPF}}'] == '12345678901'
    assert captured['tag_overrides']['{{HASH}}'] == 'TEAMHASH1234567'
```

- [ ] **Step 2: Run failing service tests**

Run: `python -m pytest tests/test_services.py::test_event_team_certificate_service_syncs_speakers_and_responsibles_without_duplicates tests/test_services.py::test_event_team_certificate_service_generates_pdf_with_team_tags -q`

Expected: FAIL with missing `app.services.event_team_certificate_service`.

- [ ] **Step 3: Implement `EventTeamCertificateService`**

Create `app/services/event_team_certificate_service.py` with these public methods and behavior:

```python
import hashlib
import json
from datetime import datetime
from types import SimpleNamespace

from app.extensions import db
from app.models import Activity, EventTeamCertificateRecipient, User
from app.services.certificate_service import CertificateService
from app.services.notification_service import NotificationService
from app.utils import build_absolute_app_url, current_certificate_issue_date_label, normalize_cpf


class EventTeamCertificateService:
    """Builds and delivers certificates for non-participant event roles."""

    def __init__(self):
        self.certificate_service = CertificateService()
        self.notifier = NotificationService()

    @staticmethod
    def _clean_text(value):
        return str(value or '').strip()

    @staticmethod
    def _clean_email(value):
        email = str(value or '').strip().lower()
        return email or None

    @staticmethod
    def normalize_workload_hours(value):
        raw = str(value or '').strip().replace(',', '.')
        if not raw:
            return None
        try:
            numeric = float(raw)
        except (TypeError, ValueError):
            return None
        if numeric < 0:
            return None
        if numeric.is_integer():
            return str(int(numeric))
        return f'{numeric:.2f}'.rstrip('0').rstrip('.')

    @staticmethod
    def build_hash(event_id, recipient_name, role_label, email=None):
        raw = f'{event_id}|{recipient_name}|{role_label}|{email or ""}|{datetime.utcnow().isoformat()}'
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16].upper()

    @classmethod
    def build_default_template(cls, bg='file/fundo_padrao.png'):
        template = CertificateService.build_default_template(designer_mode='event', bg=bg)
        for element in template.get('elements', []):
            if element.get('id') == 'txt2':
                element['text'] = 'Certificamos que {{NOME}} atuou como {{PAPEL}} no evento {{EVENTO}}{{ATIVIDADE}}, com carga horaria de {{HORAS}} horas.'
                element['w'] = 84
        return CertificateService.normalize_template_payload(template, designer_mode='event')

    @staticmethod
    def _speaker_source_key(activity, index, speaker):
        email = str(speaker.get('email') or '').strip().lower()
        name = str(speaker.get('nome') or '').strip().lower()
        identity = email or name or str(index)
        return f'speaker:{activity.id}:{identity}'

    @staticmethod
    def _responsible_source_key(username):
        return f'responsible:{username}'

    def _upsert_automatic(self, event, source_key, values):
        recipient = EventTeamCertificateRecipient.query.filter_by(
            event_id=event.id,
            source='automatico',
            source_key=source_key,
        ).first()
        created = recipient is None
        if created:
            recipient = EventTeamCertificateRecipient(event_id=event.id, source='automatico', source_key=source_key)
            db.session.add(recipient)

        recipient.nome = values['nome']
        recipient.email = values.get('email')
        recipient.cpf = values.get('cpf')
        recipient.role_label = values['role_label']
        recipient.activity_id = values.get('activity_id')
        recipient.workload_hours = values.get('workload_hours')
        return created

    def sync_event_recipients(self, event):
        created = 0
        updated = 0

        for activity in sorted(getattr(event, 'activities', []) or [], key=lambda item: item.id or 0):
            for index, speaker in enumerate(activity.get_speakers_payload(include_emails=True)):
                nome = self._clean_text(speaker.get('nome'))
                email = self._clean_email(speaker.get('email'))
                if not nome and not email:
                    continue
                source_key = self._speaker_source_key(activity, index, speaker)
                was_created = self._upsert_automatic(event, source_key, {
                    'nome': nome or email,
                    'email': email,
                    'cpf': None,
                    'role_label': 'Palestrante',
                    'activity_id': activity.id,
                    'workload_hours': self.normalize_workload_hours(activity.carga_horaria),
                })
                created += 1 if was_created else 0
                updated += 0 if was_created else 1

        for responsible in getattr(event, 'responsibles', []) or []:
            user = getattr(responsible, 'user', None)
            username = getattr(responsible, 'user_username', None) or getattr(user, 'username', None)
            if not username:
                continue
            role_label = 'Responsavel pelo evento' if getattr(responsible, 'is_primary', False) else 'Equipe organizadora'
            was_created = self._upsert_automatic(event, self._responsible_source_key(username), {
                'nome': getattr(user, 'nome', None) or username,
                'email': self._clean_email(getattr(user, 'email', None)),
                'cpf': getattr(user, 'cpf', None),
                'role_label': role_label,
                'activity_id': None,
                'workload_hours': None,
            })
            created += 1 if was_created else 0
            updated += 0 if was_created else 1

        db.session.commit()
        return {'created': created, 'updated': updated}

    def generate_recipient_pdf(self, event, recipient, template_override=None, tag_overrides=None):
        if not recipient.cert_hash:
            recipient.cert_hash = self.build_hash(event.id, recipient.nome, recipient.role_label, recipient.email)

        activity = getattr(recipient, 'activity', None)
        hours = self.normalize_workload_hours(getattr(recipient, 'workload_hours', None))
        if not hours and activity:
            hours = self.normalize_workload_hours(getattr(activity, 'carga_horaria', None))
        hours = hours or '0'
        activity_name = getattr(activity, 'nome', '') if activity else ''
        activity_text = f' na atividade {activity_name}' if activity_name else ''
        issue_date = current_certificate_issue_date_label()

        merged_tags = {
            '{{NOME}}': str(recipient.nome or '').upper(),
            '{{EVENTO}}': getattr(event, 'nome', '') or '',
            '{{PAPEL}}': recipient.role_label or '',
            '{{ATIVIDADE}}': activity_text,
            '{{HORAS}}': hours,
            '{{CPF}}': recipient.cpf or '',
            '{{HASH}}': recipient.cert_hash or '',
            '{{DATA}}': issue_date,
            '{{EMISSION_DATE}}': issue_date,
            **{str(key): '' if value is None else str(value) for key, value in (tag_overrides or {}).items()},
        }
        merged_tags['{{DATA}}'] = issue_date
        merged_tags['{{EMISSION_DATE}}'] = issue_date

        fake_event = SimpleNamespace(
            id=f'team-{event.id}',
            nome=event.nome,
            data_inicio=getattr(event, 'data_inicio', None),
            cert_bg_path=(getattr(event, 'cert_team_bg_path', None) or 'file/fundo_padrao.png'),
            cert_template_json=getattr(event, 'cert_team_template_json', None),
            designer_mode='event',
            tipo=getattr(event, 'tipo', None),
        )
        fake_user = SimpleNamespace(nome=recipient.nome, cpf=f'TEAM-{recipient.id}', email=recipient.email)
        fake_enrollment = SimpleNamespace(cert_hash=recipient.cert_hash)
        activities = [activity] if activity else []
        return self.certificate_service.generate_pdf(
            fake_event,
            fake_user,
            activities,
            hours,
            enrollment=fake_enrollment,
            template_override=template_override,
            tag_overrides=merged_tags,
        )

    def queue_email(self, event, recipient, attachment_path):
        if not recipient.email:
            return False
        cert_hash = recipient.cert_hash or ''
        return self.notifier.send_email_task(
            to_email=recipient.email,
            subject=f'Certificado de Equipe: {event.nome}',
            template_name='team_certificate_ready.html',
            template_data={
                'recipient_name': recipient.nome,
                'event_name': event.nome,
                'role_label': recipient.role_label,
                'certificate_number': cert_hash,
                'download_url': build_absolute_app_url(f'/api/certificates/team/download_public/{cert_hash}') if cert_hash else '',
                'preview_url': build_absolute_app_url(f'/api/certificates/team/preview_public/{cert_hash}') if cert_hash else '',
                'validation_url': build_absolute_app_url(f'/validar/{cert_hash}') if cert_hash else '',
            },
            attachment_path=attachment_path,
        )
```

- [ ] **Step 4: Allow `team_event` designer normalization**

In `app/services/certificate_service.py`, update `_designer_mode_for_entity` and any caller normalization so `team_event` maps to event-style fixed elements:

```python
    @classmethod
    def _designer_mode_for_entity(cls, event):
        mode = getattr(event, 'designer_mode', None)
        if mode in {'event', 'institutional', 'team_event'}:
            return 'institutional' if mode == 'institutional' else 'event'
        return 'institutional' if getattr(event, 'is_institutional_certificate', False) else 'event'
```

- [ ] **Step 5: Run service tests**

Run: `python -m pytest tests/test_services.py::test_event_team_certificate_service_syncs_speakers_and_responsibles_without_duplicates tests/test_services.py::test_event_team_certificate_service_generates_pdf_with_team_tags -q`

Expected: PASS.

- [ ] **Step 6: Checkpoint**

Run: `git diff --check`

Expected: no output.

## Task 3: Team Certificate API

**Files:**
- Modify: `app/api/certificates.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Add `EventTeamCertificateRecipient` to the imports in `tests/test_api.py`.

Append these tests:

```python
def test_team_certificate_sync_and_manual_crud(client, app, admin_user):
    seeded = _seed_certificate_management_data(app)
    _login_user(client, seeded['owner_username'])

    sync_res = client.post(f"/api/certificates/team/event/{seeded['event_id']}/sync")
    assert sync_res.status_code == 200
    assert sync_res.get_json()['created'] >= 1

    create_res = client.post(f"/api/certificates/team/event/{seeded['event_id']}/recipients", json={
        'nome': 'Facilitadora Manual',
        'email': 'facilitadora.manual@test.local',
        'cpf': '32165498700',
        'role_label': 'Facilitador',
        'activity_id': seeded['activity_id'],
        'workload_hours': '3',
    })
    assert create_res.status_code == 201
    recipient_id = create_res.get_json()['recipient']['id']

    update_res = client.put(f'/api/certificates/team/recipients/{recipient_id}', json={
        'nome': 'Facilitadora Manual Atualizada',
        'email': 'facilitadora.atualizada@test.local',
        'cpf': '32165498700',
        'role_label': 'Equipe organizadora',
        'activity_id': None,
        'workload_hours': '5',
    })
    assert update_res.status_code == 200

    list_res = client.get(f"/api/certificates/team/event/{seeded['event_id']}/recipients")
    assert list_res.status_code == 200
    items = list_res.get_json()['items']
    manual = next(item for item in items if item['id'] == recipient_id)
    assert manual['nome'] == 'Facilitadora Manual Atualizada'
    assert manual['role_label'] == 'Equipe organizadora'
    assert manual['source'] == 'manual'

    delete_res = client.delete(f'/api/certificates/team/recipients/{recipient_id}')
    assert delete_res.status_code == 200


def test_team_certificate_gestor_can_view_but_cannot_mutate(client, app, admin_user, monkeypatch, tmp_path):
    seeded = _seed_certificate_management_data(app)
    pdf_path = tmp_path / 'team.pdf'
    pdf_path.write_bytes(b'%PDF-1.4\n% mocked team certificate\n')

    with app.app_context():
        recipient = EventTeamCertificateRecipient(
            event_id=seeded['event_id'],
            activity_id=seeded['activity_id'],
            nome='Palestrante Gestor',
            email='palestrante.gestor@test.local',
            role_label='Palestrante',
            source='manual',
            cert_hash='TEAMGESTORHASH1',
        )
        db.session.add(recipient)
        db.session.commit()
        recipient_id = recipient.id

    monkeypatch.setattr(certificates_api.team_cert_service, 'generate_recipient_pdf', lambda *args, **kwargs: str(pdf_path))
    _login_user(client, seeded['manager_username'])

    list_res = client.get(f"/api/certificates/team/event/{seeded['event_id']}/recipients")
    preview_res = client.get(f'/api/certificates/team/recipients/{recipient_id}/preview')
    download_res = client.get(f'/api/certificates/team/recipients/{recipient_id}/download')
    create_res = client.post(f"/api/certificates/team/event/{seeded['event_id']}/recipients", json={'nome': 'Bloqueado', 'role_label': 'Equipe'})
    send_res = client.post(f'/api/certificates/team/recipients/{recipient_id}/resend')

    assert list_res.status_code == 200
    assert preview_res.status_code == 200
    assert preview_res.mimetype == 'application/pdf'
    assert download_res.status_code == 200
    assert create_res.status_code == 403
    assert send_res.status_code == 403
```

- [ ] **Step 2: Run failing API tests**

Run: `python -m pytest tests/test_api.py::test_team_certificate_sync_and_manual_crud tests/test_api.py::test_team_certificate_gestor_can_view_but_cannot_mutate -q`

Expected: FAIL with missing model import or 404 routes.

- [ ] **Step 3: Add API helpers and endpoints**

In `app/api/certificates.py`, import `datetime`, `send_file`, `EventTeamCertificateRecipient`, and `EventTeamCertificateService`. Add global service and lock/job dict:

```python
from datetime import datetime
from flask import send_file
from app.models import Event, Enrollment, User, Activity, EventTeamCertificateRecipient
from app.services.event_team_certificate_service import EventTeamCertificateService

team_cert_service = EventTeamCertificateService()
_SEND_TEAM_BATCH_JOBS = {}
_SEND_TEAM_BATCH_LOCK = Lock()
```

Add serializers and helpers:

```python
def _team_recipient_payload(recipient):
    activity = getattr(recipient, 'activity', None)
    return {
        'id': recipient.id,
        'event_id': recipient.event_id,
        'activity_id': recipient.activity_id,
        'activity_name': activity.nome if activity else None,
        'nome': recipient.nome,
        'email': recipient.email,
        'cpf': recipient.cpf,
        'role_label': recipient.role_label,
        'workload_hours': recipient.workload_hours,
        'source': recipient.source,
        'cert_hash': recipient.cert_hash,
        'cert_entregue': recipient.cert_entregue,
        'cert_data_envio': recipient.cert_data_envio.isoformat() if recipient.cert_data_envio else None,
    }


def _get_team_recipient_or_404(recipient_id):
    return _get_or_404(EventTeamCertificateRecipient, recipient_id)


def _event_for_team_recipient(recipient):
    return db.session.get(Event, recipient.event_id) if recipient else None
```

Implement endpoints with these route names and permission checks:

```python
@bp.route('/team/event/<int:event_id>/recipients', methods=['GET'])
@login_required
def list_team_recipients(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_view_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    recipients = EventTeamCertificateRecipient.query.filter_by(event_id=event_id).order_by(
        EventTeamCertificateRecipient.role_label.asc(),
        EventTeamCertificateRecipient.nome.asc(),
        EventTeamCertificateRecipient.id.asc(),
    ).all()
    return jsonify({'items': [_team_recipient_payload(item) for item in recipients], 'total': len(recipients)})


@bp.route('/team/event/<int:event_id>/sync', methods=['POST'])
@login_required
def sync_team_recipients(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_manage_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    summary = team_cert_service.sync_event_recipients(event)
    return jsonify({'mensagem': 'Destinatários sincronizados.', **summary})
```

For create/update, normalize required fields exactly:

```python
def _team_recipient_values_from_payload(payload):
    payload = payload or {}
    nome = str(payload.get('nome') or '').strip()
    role_label = str(payload.get('role_label') or '').strip()
    email = str(payload.get('email') or '').strip().lower() or None
    cpf = normalize_cpf(payload.get('cpf')) if payload.get('cpf') else None
    activity_id = payload.get('activity_id') or None
    workload_hours = team_cert_service.normalize_workload_hours(payload.get('workload_hours'))
    if not nome:
        return None, 'Nome é obrigatório.'
    if not role_label:
        return None, 'Papel é obrigatório.'
    if email and not _is_valid_email(email):
        return None, 'E-mail inválido.'
    return {
        'nome': nome,
        'role_label': role_label,
        'email': email,
        'cpf': cpf,
        'activity_id': activity_id,
        'workload_hours': workload_hours,
    }, None
```

Use `team_cert_service.generate_recipient_pdf(event, recipient)` in preview/download and `_build_pdf_preview_response` for inline preview. Public endpoints use `cert_hash` and do not require login.

- [ ] **Step 4: Run API tests**

Run: `python -m pytest tests/test_api.py::test_team_certificate_sync_and_manual_crud tests/test_api.py::test_team_certificate_gestor_can_view_but_cannot_mutate -q`

Expected: PASS.

- [ ] **Step 5: Checkpoint**

Run: `git diff --check`

Expected: no output.

## Task 4: Delivery, Email, Batch Jobs, And Public Validation

**Files:**
- Modify: `app/api/certificates.py`
- Modify: `app/main/routes.py`
- Modify: `app/templates/validation.html`
- Add: `app/templates/emails/team_certificate_ready.html`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing delivery and validation tests**

Append to `tests/test_api.py`:

```python
def test_team_certificate_resend_queues_email_and_public_validation(client, app, admin_user, monkeypatch, tmp_path):
    seeded = _seed_certificate_management_data(app)
    pdf_path = tmp_path / 'team-send.pdf'
    pdf_path.write_bytes(b'%PDF-1.4\n% mocked team certificate\n')
    sent = []

    with app.app_context():
        recipient = EventTeamCertificateRecipient(
            event_id=seeded['event_id'],
            activity_id=seeded['activity_id'],
            nome='Palestrante Publica',
            email='palestrante.publica@test.local',
            cpf='55566677788',
            role_label='Palestrante',
            workload_hours='2',
            source='manual',
            cert_hash='TEAMPUBLICHASH1',
        )
        db.session.add(recipient)
        db.session.commit()
        recipient_id = recipient.id

    monkeypatch.setattr(certificates_api.team_cert_service, 'generate_recipient_pdf', lambda *args, **kwargs: str(pdf_path))
    monkeypatch.setattr(certificates_api.team_cert_service.notifier, 'send_email_task', lambda **kwargs: sent.append(kwargs) or True)

    _login_user(client, seeded['owner_username'])
    resend_res = client.post(f'/api/certificates/team/recipients/{recipient_id}/resend')
    validation_res = client.get('/validar/TEAMPUBLICHASH1')
    public_download_res = client.get('/api/certificates/team/download_public/TEAMPUBLICHASH1')
    public_preview_res = client.get('/api/certificates/team/preview_public/TEAMPUBLICHASH1')

    assert resend_res.status_code == 200
    assert sent and sent[0]['template_name'] == 'team_certificate_ready.html'
    assert 'download_public/TEAMPUBLICHASH1' in sent[0]['template_data']['download_url']
    assert validation_res.status_code == 200
    validation_html = validation_res.get_data(as_text=True)
    assert 'Certificado de Equipe do Evento' in validation_html
    assert 'Palestrante Publica' in validation_html
    assert 'Palestrante' in validation_html
    assert public_download_res.status_code == 200
    assert public_preview_res.status_code == 200

    with app.app_context():
        saved = db.session.get(EventTeamCertificateRecipient, recipient_id)
        assert saved.cert_entregue is True
        assert saved.cert_data_envio is not None


def test_team_certificate_send_batch_runs_background_job(client, app, admin_user, monkeypatch, tmp_path):
    seeded = _seed_certificate_management_data(app)
    pdf_path = tmp_path / 'team-batch.pdf'
    pdf_path.write_bytes(b'%PDF-1.4\n% mocked team batch certificate\n')
    sent = []

    with app.app_context():
        db.session.add(EventTeamCertificateRecipient(
            event_id=seeded['event_id'],
            nome='Equipe Batch',
            email='equipe.batch@test.local',
            role_label='Equipe organizadora',
            source='manual',
            cert_hash='TEAMBATCHHASH01',
        ))
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
    payload = res.get_json()
    assert payload['job_id']
    status_res = client.get(f"/api/certificates/team/send_batch/status/{payload['job_id']}")
    assert status_res.status_code == 200
    assert status_res.get_json()['total_enviado'] == 1
    assert sent
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/test_api.py::test_team_certificate_resend_queues_email_and_public_validation tests/test_api.py::test_team_certificate_send_batch_runs_background_job -q`

Expected: FAIL with missing routes/templates.

- [ ] **Step 3: Add email template**

Create `app/templates/emails/team_certificate_ready.html`:

```html
{% extends 'emails/base.html' %}

{% block email_content %}
<h2 style="margin:0 0 10px 0; color:#0f172a; font-size:24px;">Certificado de equipe emitido</h2>
<p style="margin:0 0 14px 0;">Prezado(a) <strong>{{ recipient_name }}</strong>,</p>
<p style="margin:0 0 14px 0;">Seu certificado de atuação no evento está disponível para download.</p>

<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 14px 0; background:#f8fafc; border:1px solid #e2e8f0; border-left:4px solid #044d84; border-radius:10px;">
    <tr><td style="padding:14px;"><strong>Evento:</strong> {{ event_name }}</td></tr>
    {% if role_label %}<tr><td style="padding:0 14px 6px 14px;"><strong>Papel:</strong> {{ role_label }}</td></tr>{% endif %}
    {% if certificate_number %}<tr><td style="padding:0 14px 14px 14px;"><strong>Número:</strong> {{ certificate_number }}</td></tr>{% endif %}
</table>

<table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 10px 0;">
    <tr>
        <td style="background:#044d84; border-radius:8px;">
            <a href="{{ download_url }}" style="display:inline-block; padding:11px 18px; color:#fff; text-decoration:none; font-weight:700;">Baixar certificado (PDF)</a>
        </td>
    </tr>
</table>

{% if preview_url %}<p style="margin:0;"><a href="{{ preview_url }}" style="color:#044d84;">Visualizar certificado</a></p>{% endif %}
{% if validation_url %}<p style="margin:6px 0 0 0;"><a href="{{ validation_url }}" style="color:#044d84;">Validação pública</a></p>{% endif %}
{% endblock %}
```

- [ ] **Step 4: Add send and public endpoints**

In `app/api/certificates.py`, add `resend_team_recipient`, `download_team_public`, `preview_team_public`, batch job helpers, and `send_team_batch`. Use `datetime.utcnow()` for delivery timestamps to match institutional behavior. Return summary keys `total_enviado`, `sem_email`, and `falha_fila`.

- [ ] **Step 5: Add validation lookup**

In `app/main/routes.py`, import `EventTeamCertificateRecipient` inside `validar_hash`. After institutional lookup and before enrollment lookup, add team lookup:

```python
    team_recipient = EventTeamCertificateRecipient.query.filter_by(cert_hash=cert_hash).first()
    if team_recipient:
        event = team_recipient.event
        activity = team_recipient.activity
        data_ref = activity.data_atv if activity and activity.data_atv else (event.data_inicio if event else None)
        data_br = data_ref.strftime('%d/%m/%Y') if data_ref and getattr(data_ref, 'strftime', None) else ''
        return render_template(
            'validation.html',
            success=True,
            certificado_tipo='equipe_evento',
            nome=team_recipient.nome,
            evento=event.nome if event else 'N/A',
            data=data_br,
            horas=team_recipient.workload_hours,
            curso=team_recipient.role_label,
            papel=team_recipient.role_label,
            atividade=activity.nome if activity else None,
            signatario=None,
            cpf=team_recipient.cpf or 'N/A',
            hash=cert_hash,
        )
```

- [ ] **Step 6: Update validation template**

In `app/templates/validation.html`, add a team badge next to the institutional badge and display role/activity labels when `certificado_tipo == 'equipe_evento'`.

- [ ] **Step 7: Run delivery tests**

Run: `python -m pytest tests/test_api.py::test_team_certificate_resend_queues_email_and_public_validation tests/test_api.py::test_team_certificate_send_batch_runs_background_job -q`

Expected: PASS.

- [ ] **Step 8: Checkpoint**

Run: `git diff --check`

Expected: no output.

## Task 5: Pages, Designer Mode, And Team Delivery UI

**Files:**
- Modify: `app/main/routes.py`
- Modify: `app/templates/certificate_designer.html`
- Add: `app/templates/team_certificate_delivery.html`
- Modify: `app/templates/certificate_delivery.html`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing page tests**

Append to `tests/test_api.py`:

```python
def test_team_certificate_pages_load_for_owner_and_gestor(client, app, admin_user):
    seeded = _seed_certificate_management_data(app)

    for username in [seeded['owner_username'], seeded['manager_username']]:
        client.get('/api/logout')
        _login_user(client, username)
        delivery_res = client.get(f"/certificados_equipe/{seeded['event_id']}")
        designer_res = client.get(f"/designer_certificado_equipe/{seeded['event_id']}")

        assert delivery_res.status_code == 200
        assert 'Certificados da Equipe' in delivery_res.get_data(as_text=True)
        assert designer_res.status_code == 200
        designer_html = designer_res.get_data(as_text=True)
        assert 'team_event' in designer_html
        assert '/api/certificates/team/event' in designer_html


def test_team_certificate_designer_setup_and_preview_return_pdf(client, app, admin_user):
    seeded = _seed_certificate_management_data(app)
    _login_user(client, seeded['owner_username'])

    payload = {
        'version': 2,
        'document': {'gridSize': 2, 'snap': True, 'guides': True},
        'elements': [
            {
                'id': 'txt2',
                'type': 'text',
                'text': 'Certificamos que {{NOME}} atuou como {{PAPEL}} no evento {{EVENTO}}.',
                'x': 50,
                'y': 50,
                'w': 80,
                'h': 16,
                'font': 22,
                'color': '#111111',
                'align': 'center',
                'font_family': 'Helvetica',
                'visible': True,
            }
        ],
    }
    setup_res = client.post(f"/api/certificates/team/event/{seeded['event_id']}/setup", data={'template': json.dumps(payload)})
    preview_res = client.post(f"/api/certificates/team/event/{seeded['event_id']}/preview_layout", json={
        'template': payload,
        'preview_data': {
            '{{NOME}}': 'Integrante Preview',
            '{{PAPEL}}': 'Facilitador',
            '{{EVENTO}}': 'Evento Preview',
            '{{ATIVIDADE}}': 'Oficina Preview',
            '{{HORAS}}': '4',
            '{{CPF}}': '12345678901',
            '{{HASH}}': 'TEAMPREVIEWHASH',
        },
    })

    assert setup_res.status_code == 200
    assert preview_res.status_code == 200
    assert preview_res.mimetype == 'application/pdf'
    assert preview_res.data.startswith(b'%PDF')
```

- [ ] **Step 2: Run failing page tests**

Run: `python -m pytest tests/test_api.py::test_team_certificate_pages_load_for_owner_and_gestor tests/test_api.py::test_team_certificate_designer_setup_and_preview_return_pdf -q`

Expected: FAIL with missing pages or designer URLs.

- [ ] **Step 3: Add main routes**

In `app/main/routes.py`, add:

```python
@bp.route('/certificados_equipe/<int:event_id>')
@login_required
def certificados_equipe(event_id):
    from app.models import Event
    from app.services.event_service import EventService
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    can_manage_certificates = EventService.can_manage_event_certificates(current_user, event)
    if not EventService.can_view_event_certificates(current_user, event):
        return 'Acesso negado', 403
    return render_template('team_certificate_delivery.html', user=current_user, event=event, can_manage_certificates=can_manage_certificates)


@bp.route('/designer_certificado_equipe/<int:event_id>')
@login_required
def designer_certificado_equipe(event_id):
    from types import SimpleNamespace
    from app.models import Event
    from app.services.certificate_service import CertificateService
    from app.services.event_service import EventService
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    can_manage_certificates = EventService.can_manage_event_certificates(current_user, event)
    if not EventService.can_view_event_certificates(current_user, event):
        return 'Acesso negado', 403
    designer_event = SimpleNamespace(
        id=event.id,
        nome=event.nome,
        tipo=event.tipo,
        cert_bg_path=event.cert_team_bg_path,
        cert_template_json=event.cert_team_template_json,
    )
    return render_template(
        'certificate_designer.html',
        user=current_user,
        event=designer_event,
        designer_mode='team_event',
        can_manage_certificates=can_manage_certificates,
        fixed_validation_elements=CertificateService.get_fixed_validation_elements(designer_mode='event'),
    )
```

- [ ] **Step 4: Update designer mode**

In `app/templates/certificate_designer.html`:

- Treat `designerMode === 'team_event'` as separate URLs:

```javascript
    const apiBaseUrl = designerMode === 'institutional'
        ? apiUrl('/api/institutional_certificates')
        : (designerMode === 'team_event' ? apiUrl('/api/certificates/team') : apiUrl('/api/certificates'));
    const setupUrl = designerMode === 'institutional'
        ? `${apiBaseUrl}/${entityId}/setup`
        : (designerMode === 'team_event' ? `${apiBaseUrl}/event/${entityId}/setup` : `${apiBaseUrl}/setup/${entityId}`);
```

- Add `TAG_PAPEL` and team default text.
- Use team variable checks with `{{PAPEL}}`, `{{ATIVIDADE}}`, `{{HORAS}}`, and `{{HASH}}`.
- Change batch confirmation text for team mode to “Os certificados serão enviados agora para a equipe cadastrada do evento.”

- [ ] **Step 5: Add team delivery template**

Create `app/templates/team_certificate_delivery.html` as a focused Bootstrap table page. It must define `eventId`, `CAN_MANAGE_CERTIFICATES`, call `/api/certificates/team/event/${eventId}/recipients`, and provide buttons for sync, add manual, preview, download, send, delete, and batch send.

- [ ] **Step 6: Add navigation path**

In `app/templates/certificate_delivery.html`, add a header button linking to `url_for('main.certificados_equipe', event_id=event.id)` with text `Equipe do Evento`. Do not change participant delivery table behavior.

- [ ] **Step 7: Run page tests**

Run: `python -m pytest tests/test_api.py::test_team_certificate_pages_load_for_owner_and_gestor tests/test_api.py::test_team_certificate_designer_setup_and_preview_return_pdf -q`

Expected: PASS.

- [ ] **Step 8: Checkpoint**

Run: `git diff --check`

Expected: no output.

## Task 6: Regression Tests And Full Verification

**Files:**
- Test only unless failures reveal targeted fixes.

- [ ] **Step 1: Run focused certificate regression tests**

Run: `python -m pytest tests/test_api.py::test_certificate_setup_accepts_v2_template tests/test_api.py::test_certificate_preview_layout_returns_pdf tests/test_api.py::test_institutional_certificate_preview_layout_returns_pdf tests/test_api.py::test_certificate_management_endpoints_allow_admin_owner_course_coordinator_extensao_and_gestor_view tests/test_api.py::test_event_management_allows_gestor_certificate_visualization_but_blocks_certificate_mutations -q`

Expected: PASS.

- [ ] **Step 2: Run service certificate tests**

Run: `python -m pytest tests/test_services.py::test_certificate_service_build_template_tags_exposes_plural_speakers tests/test_services.py::test_institutional_certificate_service_generate_recipient_pdf_injects_default_recipient_tags tests/test_services.py::test_certificate_service_generate_pdf_template_override_keeps_fixed_element_geometry -q`

Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Run format check**

Run: `python -m black --check .`

Expected: PASS or list of files needing formatting. If formatting is needed, run `python -m black .`, then repeat this step.

- [ ] **Step 5: Run lint**

Run: `python -m flake8 .`

Expected: PASS.

- [ ] **Step 6: Migration sanity check**

Run: `python -m flask --app run.py db upgrade`

Expected: database upgrades through `7b2e1d4c9a0f` without errors in an environment with configured database. If local environment lacks PostgreSQL, record that the test suite uses SQLite and migration execution was not available.

- [ ] **Step 7: Final checkpoint**

Run: `git status --short`

Expected: only intentional source, migration, template, spec, and plan changes plus any pre-existing unrelated dirty files. Do not revert unrelated files.
