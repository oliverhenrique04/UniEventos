import os
import hashlib
import json
from datetime import datetime
from types import SimpleNamespace

from flask import current_app

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

    def _render_institutional_template_json(self, certificate, recipient):
        if not certificate.cert_template_json:
            return None

        try:
            template = json.loads(certificate.cert_template_json)
        except Exception:
            return certificate.cert_template_json

        metadata = self._recipient_metadata(recipient)
        carga_horaria = str(metadata.get('carga_horaria') or '-')
        curso_usuario = str(metadata.get('curso_usuario') or '-')

        placeholders = {
            '{{RECIPIENT_NAME}}': recipient.nome or '',
            '{{CERTIFICATE_TITLE}}': certificate.titulo or '',
            '{{CATEGORY}}': certificate.categoria or '',
            '{{EMISSION_DATE}}': certificate.data_emissao or '',
            '{{SIGNER}}': certificate.signer_name or 'Coordenacao de Extensao',
            '{{CARGA_HORARIA}}': carga_horaria,
            '{{CURSO_USUARIO}}': curso_usuario,
            '{{HASH}}': recipient.cert_hash or '',
            # Backward-compatible aliases
            '{{NOME}}': recipient.nome or '',
            '{{EVENTO}}': certificate.titulo or '',
            '{{HORAS}}': carga_horaria,
            '{{CURSO}}': curso_usuario,
            '{{DATA}}': certificate.data_emissao or '',
            '{{CPF}}': recipient.cpf or '',
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

    def generate_recipient_pdf(self, certificate, recipient):
        if not recipient.cert_hash:
            recipient.cert_hash = self.build_hash(certificate.id, recipient.nome, recipient.email)

        data_inicio = None
        try:
            data_inicio = datetime.strptime(certificate.data_emissao, '%Y-%m-%d').date()
        except Exception:
            data_inicio = None

        rendered_template_json = self._render_institutional_template_json(certificate, recipient)
        fake_event = SimpleNamespace(
            id=certificate.id,
            nome=certificate.titulo,
            data_inicio=data_inicio,
            cert_bg_path=certificate.cert_bg_path,
            cert_template_json=rendered_template_json,
        )
        fake_user = SimpleNamespace(
            nome=recipient.nome,
            cpf=recipient.cpf or f'INST-{recipient.id}',
            email=recipient.email,
        )
        fake_enrollment = SimpleNamespace(cert_hash=recipient.cert_hash)

        return self.event_certificate_service.generate_pdf(
            fake_event,
            fake_user,
            [],
            certificate.categoria or '-',
            enrollment=fake_enrollment,
        )

    def queue_email(self, certificate, recipient, attachment_path):
        if not recipient.email:
            return False

        subject = f"Certificado Institucional - {certificate.titulo}"
        body = (
            f"Ola {recipient.nome}, seu certificado institucional foi emitido. "
            f"Use o codigo {recipient.cert_hash} para validacao publica."
        )
        return self.notifier.send_email_task(
            to_email=recipient.email,
            subject=subject,
            body=body,
            attachment_path=attachment_path,
        )
