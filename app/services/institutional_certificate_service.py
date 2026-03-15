import os
import hashlib
import json
from datetime import datetime
from types import SimpleNamespace

from flask import current_app
from app.utils import build_absolute_app_url, current_certificate_issue_date_label

from app.services.certificate_service import CertificateService
from app.services.notification_service import NotificationService


class InstitutionalCertificateService:
    """Generates and queues institutional (non-event) certificates."""

    def __init__(self):
        self.notifier = NotificationService()
        self.event_certificate_service = CertificateService()

    @staticmethod
    def _replace_placeholders(text, values):
        rendered = text or ''
        for key, value in values.items():
            rendered = rendered.replace(key, value)
        return rendered

    @staticmethod
    def _recipient_metadata(recipient):
        try:
            data = json.loads(recipient.metadata_json or '{}')
            if isinstance(data, dict):
                return data
            return {}
        except Exception:
            return {}

    @staticmethod
    def _recipient_effective_profile(recipient):
        linked_user = getattr(recipient, 'linked_user', None)

        nome = (
            (linked_user.nome if linked_user else None)
            or (linked_user.username if linked_user else None)
            or recipient.nome
            or ''
        )
        email = (
            (linked_user.email.lower() if linked_user and linked_user.email else None)
            or recipient.email
            or None
        )
        cpf = (
            (linked_user.cpf if linked_user else None)
            or recipient.cpf
            or None
        )

        return {
            'nome': nome,
            'email': email,
            'cpf': cpf,
        }

    def _render_institutional_template_json(self, certificate, recipient):
        if not certificate.cert_template_json:
            return None

        try:
            template = json.loads(certificate.cert_template_json)
        except Exception:
            return certificate.cert_template_json

        metadata = self._recipient_metadata(recipient)
        profile = self._recipient_effective_profile(recipient)
        carga_horaria = str(metadata.get('carga_horaria') or '-')
        curso_usuario = str(metadata.get('curso_usuario') or '-')
        issue_date = current_certificate_issue_date_label()

        placeholders = {
            '{{RECIPIENT_NAME}}': profile['nome'] or '',
            '{{CERTIFICATE_TITLE}}': certificate.titulo or '',
            '{{CATEGORY}}': certificate.categoria or '',
            '{{EMISSION_DATE}}': issue_date,
            '{{SIGNER}}': certificate.signer_name or 'Coordenacao de Extensao',
            '{{CARGA_HORARIA}}': carga_horaria,
            '{{CURSO_USUARIO}}': curso_usuario,
            '{{HASH}}': recipient.cert_hash or '',
            # Backward-compatible aliases
            '{{NOME}}': profile['nome'] or '',
            '{{EVENTO}}': certificate.titulo or '',
            '{{HORAS}}': carga_horaria,
            '{{CURSO}}': curso_usuario,
            '{{DATA}}': issue_date,
            '{{DATA_REALIZACAO}}': '',
            '{{CPF}}': profile['cpf'] or '',
        }

        for element in template.get('elements', []):
            if not isinstance(element, dict):
                continue
            if isinstance(element.get('text'), str):
                element['text'] = self._replace_placeholders(element['text'], placeholders)
            if isinstance(element.get('html_content'), str):
                element['html_content'] = self._replace_placeholders(element['html_content'], placeholders)

        return json.dumps(template, ensure_ascii=False)

    def build_hash(self, certificate_id, recipient_name, recipient_email=None):
        raw = f"{certificate_id}|{recipient_name}|{recipient_email or ''}|{datetime.utcnow().isoformat()}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16].upper()

    def generate_recipient_pdf(self, certificate, recipient, template_override=None, tag_overrides=None):
        profile = self._recipient_effective_profile(recipient)
        metadata = self._recipient_metadata(recipient)

        if not recipient.cert_hash:
            recipient.cert_hash = self.build_hash(certificate.id, profile['nome'], profile['email'])

        data_inicio = None
        try:
            data_inicio = datetime.strptime(certificate.data_emissao, '%Y-%m-%d').date()
        except Exception:
            data_inicio = None

        rendered_template_json = self._render_institutional_template_json(certificate, recipient)
        carga_horaria = str(metadata.get('carga_horaria') or '-')
        curso_usuario = str(metadata.get('curso_usuario') or '-')
        issue_date = current_certificate_issue_date_label()
        default_tag_overrides = {
            '{{RECIPIENT_NAME}}': profile['nome'] or '',
            '{{CERTIFICATE_TITLE}}': certificate.titulo or '',
            '{{CATEGORY}}': certificate.categoria or '',
            '{{EMISSION_DATE}}': issue_date,
            '{{SIGNER}}': certificate.signer_name or 'Coordenacao de Extensao',
            '{{CARGA_HORARIA}}': carga_horaria,
            '{{CURSO_USUARIO}}': curso_usuario,
            '{{HASH}}': recipient.cert_hash or '',
            # Backward-compatible aliases
            '{{NOME}}': profile['nome'] or '',
            '{{EVENTO}}': certificate.titulo or '',
            '{{HORAS}}': carga_horaria,
            '{{CURSO}}': curso_usuario,
            '{{DATA}}': issue_date,
            '{{DATA_REALIZACAO}}': '',
            '{{CPF}}': profile['cpf'] or '',
        }
        merged_tag_overrides = {
            **default_tag_overrides,
            **{str(key): '' if value is None else str(value) for key, value in (tag_overrides or {}).items()},
        }
        merged_tag_overrides['{{DATA}}'] = issue_date
        merged_tag_overrides['{{EMISSION_DATE}}'] = issue_date
        merged_tag_overrides['{{DATA_REALIZACAO}}'] = ''
        fake_event = SimpleNamespace(
            id=certificate.id,
            nome=certificate.titulo,
            titulo=certificate.titulo,
            categoria=certificate.categoria,
            data_emissao=certificate.data_emissao,
            signer_name=certificate.signer_name,
            data_inicio=data_inicio,
            cert_bg_path=certificate.cert_bg_path,
            cert_template_json=rendered_template_json,
            designer_mode='institutional',
            is_institutional_certificate=True,
        )
        fake_user = SimpleNamespace(
            nome=profile['nome'],
            cpf=profile['cpf'] or f'INST-{recipient.id}',
            email=profile['email'],
        )
        fake_enrollment = SimpleNamespace(cert_hash=recipient.cert_hash)

        return self.event_certificate_service.generate_pdf(
            fake_event,
            fake_user,
            [],
            certificate.categoria or '-',
            enrollment=fake_enrollment,
            template_override=template_override,
            tag_overrides=merged_tag_overrides,
        )

    def queue_email(self, certificate, recipient, attachment_path):
        profile = self._recipient_effective_profile(recipient)
        if not profile['email']:
            return False

        subject = f"Certificado Institucional - {certificate.titulo}"
        return self.notifier.send_email_task(
            to_email=profile['email'],
            subject=subject,
            template_name='institutional_certificate_ready.html',
            template_data={
                'recipient_name': profile['nome'],
                'certificate_title': certificate.titulo,
                'category_name': certificate.categoria,
                'issue_date': current_certificate_issue_date_label(),
                'certificate_number': recipient.cert_hash,
                'signer_name': certificate.signer_name,
                'recipient_cpf': profile['cpf'],
                'download_url': build_absolute_app_url(f"/api/institutional_certificates/download_public/{recipient.cert_hash}"),
                'preview_url': build_absolute_app_url(f"/api/institutional_certificates/preview_public/{recipient.cert_hash}"),
                'validation_url': build_absolute_app_url(f"/validar/{recipient.cert_hash}"),
            },
            attachment_path=attachment_path,
        )
