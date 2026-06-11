import hashlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.utils import build_absolute_app_url, current_certificate_issue_date_label

from app.services.certificate_service import CertificateService
from app.services.notification_service import NotificationService
from app.models import EventTeamCertificateRecipient
from app.extensions import db


class EventTeamCertificateService:

    def __init__(self):
        self.certificate_service = CertificateService()
        self.notifier = NotificationService()

    @staticmethod
    def build_hash(event_id, recipient_name, role_label, email=None):
        issued_at = datetime.now(timezone.utc).isoformat()
        raw = f"{event_id}|{recipient_name}|{role_label}|{email or ''}|{issued_at}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16].upper()

    @staticmethod
    def normalize_workload_hours(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if value < 0:
                return None
            return str(value)
        if isinstance(value, str):
            stripped = value.strip().replace(',', '.')
            if not stripped:
                return None
            try:
                num = float(stripped)
                if num < 0:
                    return None
                if num == int(num):
                    return str(int(num))
                return str(num)
            except ValueError:
                return None
        return None

    @staticmethod
    def _speaker_source_key(activity_id, email, nome):
        identifier = (email or '').strip().lower() or (nome or '').strip().lower()
        return f"speaker:{activity_id}:{identifier}"

    @staticmethod
    def _responsible_source_key(username):
        return f"responsible:{username}"

    def resolve_event_recipients(self, event):
        resolved = []
        automatic_rows = {
            item.source_key: item
            for item in event.team_certificate_recipients
            if item.source == 'automatico' and item.source_key
        }
        consumed_automatic_keys = set()

        for activity in event.activities:
            for speaker in activity.speakers:
                speaker_name = (speaker.nome or '').strip()
                if not speaker_name:
                    continue
                speaker_email = (speaker.email or '').strip() or None
                source_key = self._speaker_source_key(activity.id, speaker_email, speaker_name)
                persisted = automatic_rows.get(source_key)
                consumed_automatic_keys.add(source_key)
                hours = self.normalize_workload_hours(activity.carga_horaria)
                resolved.append({
                    'source': 'activity',
                    'event_id': event.id,
                    'activity_id': activity.id,
                    'activity_name': activity.nome or '',
                    'nome': speaker_name,
                    'email': speaker_email,
                    'cpf': None,
                    'role_label': 'Palestrante',
                    'workload_hours': hours,
                    'source_key': source_key,
                    'cert_hash': persisted.cert_hash if persisted else None,
                    'cert_entregue': bool(persisted.cert_entregue) if persisted else False,
                    'cert_data_envio': persisted.cert_data_envio.isoformat() if persisted and persisted.cert_data_envio else None,
                    'id': persisted.id if persisted else None,
                })

        for responsible in event.responsibles:
            user = responsible.user
            user_name = user.nome if user and user.nome else ''
            if not user_name:
                continue
            user_email = (user.email or '').strip() if user and user.email else None
            source_key = self._responsible_source_key(responsible.user_username)
            persisted = automatic_rows.get(source_key)
            consumed_automatic_keys.add(source_key)
            role_label = 'Responsavel pelo evento' if responsible.is_primary else 'Equipe organizadora'
            resolved.append({
                'source': 'responsible',
                'event_id': event.id,
                'activity_id': None,
                'activity_name': None,
                'nome': user_name,
                'email': user_email,
                'cpf': user.cpf if user else None,
                'role_label': role_label,
                'workload_hours': None,
                'source_key': source_key,
                'cert_hash': persisted.cert_hash if persisted else None,
                'cert_entregue': bool(persisted.cert_entregue) if persisted else False,
                'cert_data_envio': persisted.cert_data_envio.isoformat() if persisted and persisted.cert_data_envio else None,
                'id': persisted.id if persisted else None,
            })

        for recipient in event.team_certificate_recipients:
            if recipient.source != 'manual':
                continue
            activity = getattr(recipient, 'activity', None)
            resolved.append({
                'source': 'manual',
                'event_id': recipient.event_id,
                'activity_id': recipient.activity_id,
                'activity_name': activity.nome if activity else None,
                'nome': recipient.nome,
                'email': recipient.email,
                'cpf': recipient.cpf,
                'role_label': recipient.role_label,
                'workload_hours': recipient.workload_hours,
                'source_key': None,
                'cert_hash': recipient.cert_hash,
                'cert_entregue': bool(recipient.cert_entregue),
                'cert_data_envio': recipient.cert_data_envio.isoformat() if recipient.cert_data_envio else None,
                'id': recipient.id,
            })

        for source_key, recipient in automatic_rows.items():
            if source_key in consumed_automatic_keys:
                continue
            activity = getattr(recipient, 'activity', None)
            resolved.append({
                'source': 'automatico',
                'event_id': recipient.event_id,
                'activity_id': recipient.activity_id,
                'activity_name': activity.nome if activity else None,
                'nome': recipient.nome,
                'email': recipient.email,
                'cpf': recipient.cpf,
                'role_label': recipient.role_label,
                'workload_hours': recipient.workload_hours,
                'source_key': recipient.source_key,
                'cert_hash': recipient.cert_hash,
                'cert_entregue': bool(recipient.cert_entregue),
                'cert_data_envio': recipient.cert_data_envio.isoformat() if recipient.cert_data_envio else None,
                'id': recipient.id,
            })

        for row in resolved:
            row['resolved_key'] = self.build_resolved_key(row)

        resolved.sort(key=lambda r: (r['role_label'] or '', r['nome'] or '', r['activity_name'] or ''))

        return resolved

    @staticmethod
    def build_resolved_key(row):
        parts = [
            row.get('source') or '',
            str(row.get('event_id') or ''),
            str(row.get('activity_id') or ''),
            (row.get('nome') or '').strip(),
            (row.get('email') or '').strip(),
            (row.get('role_label') or '').strip(),
        ]
        digest = hashlib.sha256('|'.join(parts).encode('utf-8')).hexdigest()[:16]
        return f"{parts[0]}|{parts[1]}|{digest}"

    def sync_event_recipients(self, event):
        max_retries = 1
        for attempt in range(max_retries + 1):
            created = 0
            updated = 0
            try:
                for activity in event.activities:
                    for speaker in activity.speakers:
                        speaker_name = (speaker.nome or '').strip()
                        if not speaker_name:
                            continue
                        speaker_email = (speaker.email or '').strip() or None
                        source_key = self._speaker_source_key(activity.id, speaker_email, speaker_name)
                        hours = self.normalize_workload_hours(activity.carga_horaria)

                        existing = EventTeamCertificateRecipient.query.filter_by(
                            event_id=event.id,
                            source='automatico',
                            source_key=source_key,
                        ).first()

                        if existing:
                            existing.nome = speaker_name
                            existing.email = speaker_email
                            existing.role_label = 'Palestrante'
                            existing.workload_hours = hours
                            existing.activity_id = activity.id
                            updated += 1
                        else:
                            recipient = EventTeamCertificateRecipient(
                                event_id=event.id,
                                activity_id=activity.id,
                                nome=speaker_name,
                                email=speaker_email,
                                role_label='Palestrante',
                                workload_hours=hours,
                                source='automatico',
                                source_key=source_key,
                            )
                            db.session.add(recipient)
                            created += 1

                for responsible in event.responsibles:
                    user = responsible.user
                    user_name = user.nome if user and user.nome else ''
                    if not user_name:
                        continue
                    user_email = (user.email or '').strip() if user and user.email else None
                    source_key = self._responsible_source_key(responsible.user_username)
                    role_label = 'Responsavel pelo evento' if responsible.is_primary else 'Equipe organizadora'

                    existing = EventTeamCertificateRecipient.query.filter_by(
                        event_id=event.id,
                        source='automatico',
                        source_key=source_key,
                    ).first()

                    if existing:
                        existing.nome = user_name
                        existing.email = user_email
                        existing.cpf = user.cpf if user and user.cpf else existing.cpf
                        existing.role_label = role_label
                        updated += 1
                    else:
                        recipient = EventTeamCertificateRecipient(
                            event_id=event.id,
                            activity_id=None,
                            nome=user_name,
                            email=user_email,
                            cpf=user.cpf if user else None,
                            role_label=role_label,
                            workload_hours=None,
                            source='automatico',
                            source_key=source_key,
                        )
                        db.session.add(recipient)
                        created += 1

                db.session.commit()
                return {'created': created, 'updated': updated}
            except IntegrityError:
                db.session.rollback()
                if attempt == max_retries:
                    raise

    def build_virtual_recipient(self, event, resolved_row):
        if resolved_row is None:
            return None
        activity_id = resolved_row.get('activity_id')
        activity = None
        if activity_id is not None:
            for act in event.activities:
                if act.id == activity_id:
                    activity = act
                    break
        workload_hours = resolved_row.get('workload_hours') or self.normalize_workload_hours(
            getattr(activity, 'carga_horaria', None) if activity else None
        )
        return SimpleNamespace(
            id=resolved_row.get('id'),
            nome=resolved_row['nome'],
            email=resolved_row.get('email'),
            cpf=resolved_row.get('cpf'),
            role_label=resolved_row['role_label'],
            workload_hours=workload_hours,
            cert_hash=resolved_row.get('cert_hash'),
            activity=activity,
            cert_entregue=resolved_row.get('cert_entregue', False),
            cert_data_envio=resolved_row.get('cert_data_envio'),
        )

    def ensure_persisted_automatic_recipient(self, event, resolved_row):
        if not resolved_row or resolved_row.get('id') is not None or resolved_row.get('source') == 'manual':
            return resolved_row

        source_key = resolved_row.get('source_key')
        if not source_key:
            return resolved_row

        persisted = EventTeamCertificateRecipient.query.filter_by(
            event_id=event.id,
            source='automatico',
            source_key=source_key,
        ).first()
        if not persisted:
            persisted = EventTeamCertificateRecipient(
                event_id=event.id,
                activity_id=resolved_row.get('activity_id'),
                nome=resolved_row.get('nome') or '',
                email=resolved_row.get('email'),
                cpf=resolved_row.get('cpf'),
                role_label=resolved_row.get('role_label') or '',
                workload_hours=resolved_row.get('workload_hours'),
                source='automatico',
                source_key=source_key,
            )
            db.session.add(persisted)
            db.session.flush()

        persisted.activity_id = resolved_row.get('activity_id')
        persisted.nome = resolved_row.get('nome') or persisted.nome
        persisted.email = resolved_row.get('email') or persisted.email
        persisted.cpf = resolved_row.get('cpf')
        persisted.role_label = resolved_row.get('role_label') or persisted.role_label
        persisted.workload_hours = resolved_row.get('workload_hours')

        resolved_row['id'] = persisted.id
        resolved_row['cert_hash'] = persisted.cert_hash
        resolved_row['cert_entregue'] = bool(persisted.cert_entregue)
        resolved_row['cert_data_envio'] = persisted.cert_data_envio.isoformat() if persisted.cert_data_envio else None
        return resolved_row

    def ensure_recipient_hash(self, event_id, resolved_row):
        if not resolved_row or resolved_row.get('cert_hash'):
            return resolved_row

        cert_hash = self.build_hash(
            event_id,
            resolved_row.get('nome'),
            resolved_row.get('role_label'),
            resolved_row.get('email'),
        )
        resolved_row['cert_hash'] = cert_hash

        resolved_id = resolved_row.get('id')
        if resolved_id is not None:
            persisted = db.session.get(EventTeamCertificateRecipient, resolved_id)
            if persisted and not persisted.cert_hash:
                persisted.cert_hash = cert_hash

        return resolved_row

    def build_default_team_template(self, event):
        fixed_elements = self.certificate_service.get_fixed_validation_elements(designer_mode='team_event')
        background = (
            getattr(event, 'cert_team_bg_path', None) or
            getattr(event, 'cert_bg_path', None) or
            self.certificate_service.DEFAULT_BACKGROUND_PATH
        )
        team_text_element = {
            'id': 'txt2',
            'type': 'text',
            'text': (
                'Certificamos que {{NOME}}, CPF {{CPF}}, atuou como {{PAPEL}} '
                'no evento {{EVENTO}} na data {{DATA_REALIZACAO}}.'
            ),
            'x': 50,
            'y': 50,
            'w': 82,
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
        return {
            'version': 2,
            'document': {'gridSize': 2, 'snap': True, 'guides': True},
            'bg': str(background).strip(),
            'elements': [team_text_element] + json.loads(json.dumps(fixed_elements)),
        }

    def generate_recipient_pdf(self, event, recipient, template_override=None, tag_overrides=None):
        activity = getattr(recipient, 'activity', None)
        activity_name = activity.nome if activity and getattr(activity, 'nome', None) else ''

        if recipient.workload_hours not in (None, ''):
            workload_hours = recipient.workload_hours
        else:
            workload_hours = self.normalize_workload_hours(
                getattr(activity, 'carga_horaria', None) if activity else None
            )
        total_hours = workload_hours or '0'

        if not recipient.cert_hash:
            recipient.cert_hash = self.build_hash(
                event.id, recipient.nome, recipient.role_label, recipient.email
            )
            db.session.commit()

        team_template_json = getattr(event, 'cert_team_template_json', None)
        team_bg_path = self.certificate_service._background_for_entity(event, designer_mode='team_event') or ''

        issue_date = current_certificate_issue_date_label()

        default_tag_overrides = {
            '{{PAPEL}}': recipient.role_label or '',
            '{{ATIVIDADE}}': activity_name,
            '{{HORAS}}': total_hours,
            '{{CPF}}': recipient.cpf or '',
            '{{HASH}}': recipient.cert_hash or '',
            '{{DATA}}': issue_date,
            '{{EMISSION_DATE}}': issue_date,
        }
        merged_overrides = {
            **default_tag_overrides,
            **{str(k): '' if v is None else str(v) for k, v in (tag_overrides or {}).items()},
        }
        merged_overrides['{{DATA}}'] = issue_date
        merged_overrides['{{EMISSION_DATE}}'] = issue_date

        fake_event = SimpleNamespace(
            id=f"team-{event.id}",
            nome=getattr(event, 'nome', ''),
            data_inicio=getattr(event, 'data_inicio', None),
            cert_bg_path=team_bg_path,
            cert_template_json=team_template_json,
            designer_mode='event',
        )
        fake_user = SimpleNamespace(
            id=recipient.id,
            nome=recipient.nome,
            cpf=f"TEAM-{recipient.id}",
            email=recipient.email or '',
        )
        fake_enrollment = SimpleNamespace(cert_hash=recipient.cert_hash)

        return self.certificate_service.generate_pdf(
            fake_event,
            fake_user,
            [activity] if activity else [],
            total_hours,
            enrollment=fake_enrollment,
            template_override=template_override,
            tag_overrides=merged_overrides,
        )

    def queue_email(self, event, recipient, attachment_path):
        if not recipient.email:
            return False
        event_name = getattr(event, 'nome', '')
        subject = f"Certificado de Equipe - {event_name}"
        return self.notifier.send_email_task(
            to_email=recipient.email,
            subject=subject,
            template_name='team_certificate_ready.html',
            template_data={
                'recipient_name': recipient.nome,
                'event_name': event_name,
                'role_label': recipient.role_label,
                'certificate_number': recipient.cert_hash,
                'download_url': build_absolute_app_url(f"/api/certificates/team/download_public/{recipient.cert_hash}"),
                'preview_url': build_absolute_app_url(f"/api/certificates/team/preview_public/{recipient.cert_hash}"),
                'validation_url': build_absolute_app_url(f"/validar/{recipient.cert_hash}"),
            },
            attachment_path=attachment_path,
        )
