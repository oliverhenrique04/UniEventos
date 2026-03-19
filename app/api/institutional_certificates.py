import json
from datetime import datetime
import re
import csv
import io
import os
import time
from threading import Lock, Thread
from uuid import uuid4
from types import SimpleNamespace

from flask import Blueprint, jsonify, request, make_response, send_file, current_app
from flask import url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, func
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import (
    InstitutionalCertificate,
    InstitutionalCertificateRecipient,
    InstitutionalCertificateCategory,
    User,
    Course,
    Event,
    Activity,
    Enrollment,
)
from app.services.institutional_certificate_service import InstitutionalCertificateService
from app.services.certificate_service import CertificateService

bp = Blueprint('institutional_certificates', __name__, url_prefix='/api/institutional_certificates')
institutional_service = InstitutionalCertificateService()
_SEND_CERTIFICATE_JOBS = {}
_SEND_CERTIFICATE_LOCK = Lock()

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
MAX_DESIGN_IMAGE_SIZE = 8 * 1024 * 1024


def _can_manage_institutional_certificates():
    return current_user.role in ['admin', 'extensao', 'gestor']


def _can_view_institutional_certificates():
    return current_user.role in ['admin', 'extensao', 'gestor', 'coordenador']


def _can_edit_institutional_certificate(cert):
    if current_user.role in ['admin', 'extensao']:
        return True
    if current_user.role == 'gestor':
        return cert.created_by_username == current_user.username
    return False


def _can_delete_institutional_certificate(cert):
    if current_user.role == 'admin':
        return True
    if current_user.role in ['extensao', 'gestor']:
        return cert.created_by_username == current_user.username
    return False


def _get_institutional_certificate_delete_block_status(cert):
    if not cert:
        return {
            'linked_recipients_count': 0,
            'has_linked_records': False,
            'delete_block_reason': None,
        }

    linked_recipients_count = InstitutionalCertificateRecipient.query.filter_by(
        certificate_id=cert.id
    ).count()
    has_linked_records = linked_recipients_count > 0

    return {
        'linked_recipients_count': linked_recipients_count,
        'has_linked_records': has_linked_records,
        'delete_block_reason': (
            'Não é possível excluir o certificado porque existem destinatários vinculados.'
            if has_linked_records else None
        ),
    }


def _coordinator_course_id():
    if current_user.role != 'coordenador':
        return None
    return getattr(current_user, 'course_id', None)


def _build_coordinator_visible_certificate_ids_query():
    course_id = _coordinator_course_id()
    if not course_id:
        return None
    return (
        db.session.query(InstitutionalCertificateRecipient.certificate_id)
        .join(User, InstitutionalCertificateRecipient.user_username == User.username)
        .filter(User.course_id == course_id)
        .distinct()
    )


def _apply_institutional_certificate_view_scope(query):
    if current_user.role != 'coordenador':
        return query

    visible_ids = _build_coordinator_visible_certificate_ids_query()
    if visible_ids is None:
        return query.filter(InstitutionalCertificate.id.is_(None))
    return query.filter(InstitutionalCertificate.id.in_(visible_ids))


def _apply_institutional_recipient_view_scope(query):
    if current_user.role != 'coordenador':
        return query

    course_id = _coordinator_course_id()
    if not course_id:
        return query.filter(InstitutionalCertificateRecipient.id.is_(None))
    return query.join(User, InstitutionalCertificateRecipient.user_username == User.username).filter(
        User.course_id == course_id
    )


def _can_view_institutional_certificate(cert):
    if not cert:
        return False
    if current_user.role in ['admin', 'extensao', 'gestor']:
        return True
    if current_user.role != 'coordenador':
        return False

    course_id = _coordinator_course_id()
    if not course_id:
        return False

    return db.session.query(InstitutionalCertificateRecipient.id).join(
        User,
        InstitutionalCertificateRecipient.user_username == User.username,
    ).filter(
        InstitutionalCertificateRecipient.certificate_id == cert.id,
        User.course_id == course_id,
    ).first() is not None


def _can_view_institutional_certificate_designer(cert):
    if _can_edit_institutional_certificate(cert):
        return True
    if current_user.role == 'coordenador':
        return _can_view_institutional_certificate(cert)
    return False


def _count_visible_recipients(certificate_id):
    return _apply_institutional_recipient_view_scope(
        InstitutionalCertificateRecipient.query.filter_by(certificate_id=certificate_id)
    ).count()


def _serialize_institutional_certificate_payload(cert, include_template=False):
    delete_permission = _can_delete_institutional_certificate(cert)
    delete_block_status = _get_institutional_certificate_delete_block_status(cert)
    payload = {
        'id': cert.id,
        'titulo': cert.titulo,
        'categoria': cert.categoria,
        'category_id': cert.category_id,
        'descricao': cert.descricao,
        'data_emissao': cert.data_emissao,
        'signer_name': cert.signer_name,
        'cert_bg_path': cert.cert_bg_path,
        'status': cert.status,
        'created_by_username': cert.created_by_username,
        'created_by_name': cert.creator.nome if cert.creator else None,
        'recipients_count': _count_visible_recipients(cert.id),
        'linked_recipients_count': delete_block_status['linked_recipients_count'],
        'has_linked_records': delete_block_status['has_linked_records'],
        'delete_block_reason': (
            'Sem permissão para excluir este certificado.'
            if not delete_permission
            else delete_block_status['delete_block_reason']
        ),
        'can_edit': _can_edit_institutional_certificate(cert),
        'can_delete_permission': delete_permission,
        'can_delete': delete_permission and not delete_block_status['has_linked_records'],
        'can_view_designer': _can_view_institutional_certificate_designer(cert),
    }
    if cert.created_at:
        payload['created_at'] = cert.created_at.isoformat()
    if include_template:
        payload['template'] = json.loads(cert.cert_template_json or '{}')
    return payload


def _parse_date_iso(date_str):
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except (TypeError, ValueError):
        return False


def _is_valid_email(email):
    if not email:
        return False
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def _is_allowed_image(filename):
    _, ext = os.path.splitext((filename or '').lower())
    return ext in ALLOWED_IMAGE_EXTENSIONS


def _validate_image_file(file_storage):
    if not file_storage or not file_storage.filename:
        return False, 'Arquivo nao enviado'

    if not _is_allowed_image(file_storage.filename):
        return False, 'Formato invalido. Use PNG, JPG, JPEG ou WEBP'

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)

    if size <= 0:
        return False, 'Arquivo vazio'
    if size > MAX_DESIGN_IMAGE_SIZE:
        return False, 'Arquivo excede o limite de 8MB'

    return True, None


def _sanitize_html_content(html_content):
    if not html_content or not isinstance(html_content, str):
        return html_content

    html_content = re.sub(
        r'<(script|iframe|object|embed|frame|frameset|applet|meta|link|style)[^>]*>.*?</\1>',
        '', html_content, flags=re.DOTALL | re.IGNORECASE
    )
    html_content = re.sub(
        r'<(script|iframe|meta|link|style|base)[^>]*/?>',
        '', html_content, flags=re.IGNORECASE
    )
    html_content = re.sub(
        r'\s+on\w+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)',
        '', html_content, flags=re.IGNORECASE
    )
    html_content = re.sub(
        r'(href|src)\s*=\s*["\']?\s*(javascript|data):[^"\'>\s]*["\']?',
        '', html_content, flags=re.IGNORECASE
    )
    return html_content


def _normalize_template(template_json, designer_mode='institutional'):
    if template_json is None:
        return None, None

    normalized, error = _normalize_template_payload(template_json, designer_mode=designer_mode)
    if error:
        return None, error
    return json.dumps(normalized, ensure_ascii=False), None


def _normalize_template_payload(template_source, designer_mode='institutional'):
    if template_source is None:
        return None, None

    parsed = template_source
    if isinstance(template_source, str):
        try:
            parsed = json.loads(template_source)
        except (ValueError, TypeError):
            return None, 'Template invalido: JSON malformado'

    if not isinstance(parsed, dict):
        return None, 'Template invalido: estrutura esperada e um objeto'

    for element in parsed.get('elements', []):
        if element.get('is_html') and element.get('html_content'):
            element['html_content'] = _sanitize_html_content(element['html_content'])

    return CertificateService.normalize_template_payload(parsed, designer_mode=designer_mode), None


def _build_pdf_preview_response(pdf_path):
    response = send_file(pdf_path, mimetype='application/pdf', conditional=False, max_age=0)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


def _normalize_workload_hours(value):
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
    return f"{numeric:.2f}".rstrip('0').rstrip('.')


def _extract_recipient_metadata(recipient):
    try:
        metadata = json.loads(recipient.metadata_json or '{}')
        if not isinstance(metadata, dict):
            return {}
        return metadata
    except Exception:
        return {}


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
    username = (linked_user.username if linked_user else None) or recipient.user_username

    return {
        'nome': nome,
        'email': email,
        'cpf': cpf,
        'user_username': username,
    }


def _to_float_or_none(value):
    raw = str(value or '').strip().replace(',', '.')
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _get_managed_certificate_or_error(certificate_id):
    cert = db.session.get(InstitutionalCertificate, certificate_id)
    if not cert:
        return None, (jsonify({'erro': 'Nao encontrado'}), 404)
    if not _can_view_institutional_certificates():
        return None, (jsonify({'erro': 'Permissao negada'}), 403)
    if not _can_edit_institutional_certificate(cert):
        return None, (jsonify({'erro': 'Acesso negado'}), 403)
    return cert, None


def _get_deletable_certificate_or_error(certificate_id):
    cert = db.session.get(InstitutionalCertificate, certificate_id)
    if not cert:
        return None, (jsonify({'erro': 'Nao encontrado'}), 404)
    if not _can_view_institutional_certificates():
        return None, (jsonify({'erro': 'Permissao negada'}), 403)
    if not _can_delete_institutional_certificate(cert):
        return None, (jsonify({'erro': 'Acesso negado'}), 403)
    return cert, None


def _get_viewable_certificate_or_error(certificate_id):
    cert = db.session.get(InstitutionalCertificate, certificate_id)
    if not cert:
        return None, (jsonify({'erro': 'Nao encontrado'}), 404)
    if not _can_view_institutional_certificates():
        return None, (jsonify({'erro': 'Permissao negada'}), 403)
    if not _can_view_institutional_certificate(cert):
        return None, (jsonify({'erro': 'Acesso negado'}), 403)
    return cert, None


def _get_designer_viewable_certificate_or_error(certificate_id):
    cert = db.session.get(InstitutionalCertificate, certificate_id)
    if not cert:
        return None, (jsonify({'erro': 'Nao encontrado'}), 404)
    if not _can_view_institutional_certificates():
        return None, (jsonify({'erro': 'Permissao negada'}), 403)
    if not _can_view_institutional_certificate_designer(cert):
        return None, (jsonify({'erro': 'Acesso negado'}), 403)
    return cert, None


def _get_viewable_recipient_or_error(certificate_id, recipient_id):
    cert, error = _get_viewable_certificate_or_error(certificate_id)
    if error:
        return None, None, error

    recipient = _apply_institutional_recipient_view_scope(
        InstitutionalCertificateRecipient.query.filter_by(certificate_id=certificate_id)
    ).filter(
        InstitutionalCertificateRecipient.id == recipient_id
    ).first()
    if not recipient:
        return cert, None, (jsonify({'erro': 'Destinatario nao encontrado'}), 404)
    return cert, recipient, None


def _get_active_send_job(certificate_id, created_by):
    for job in _SEND_CERTIFICATE_JOBS.values():
        if job.get('certificate_id') != certificate_id:
            continue
        if job.get('created_by') != created_by:
            continue
        if not job.get('completed'):
            return job
    return None


def _update_send_job(job_id, **kwargs):
    with _SEND_CERTIFICATE_LOCK:
        job = _SEND_CERTIFICATE_JOBS.get(job_id)
        if not job:
            return None
        job.update(kwargs)
        job['updated_at'] = time.time()
        return dict(job)


def _send_institutional_certificates_sync(certificate_id):
    cert = db.session.get(InstitutionalCertificate, certificate_id)
    if not cert:
        return False, 'Certificado não encontrado', {
            'total_enviado': 0,
            'sem_email': 0,
            'falha_fila': 0,
        }

    recipients = InstitutionalCertificateRecipient.query.filter_by(certificate_id=certificate_id).all()
    if not recipients:
        return False, 'Nenhum destinatario cadastrado', {
            'total_enviado': 0,
            'sem_email': 0,
            'falha_fila': 0,
        }

    sent_count = 0
    skipped_without_email = 0
    failed_queue = 0
    now = datetime.utcnow()
    for recipient in recipients:
        profile = _recipient_effective_profile(recipient)
        if not recipient.cert_hash:
            recipient.cert_hash = institutional_service.build_hash(certificate_id, profile['nome'], profile['email'])

        if not profile['email']:
            skipped_without_email += 1
            continue

        pdf_path = institutional_service.generate_recipient_pdf(cert, recipient)
        queued = institutional_service.queue_email(cert, recipient, pdf_path)
        if not queued:
            failed_queue += 1
            continue

        recipient.cert_entregue = True
        recipient.cert_data_envio = now
        sent_count += 1

    cert.status = 'ENVIADO' if sent_count > 0 else cert.status
    db.session.commit()

    if sent_count == 0 and failed_queue > 0:
        return False, 'Problema no envio: falha ao enfileirar e-mails.', {
            'total_enviado': sent_count,
            'sem_email': skipped_without_email,
            'falha_fila': failed_queue,
        }

    if sent_count == 0:
        return False, 'Problema no envio: nenhum destinatario com email valido', {
            'total_enviado': sent_count,
            'sem_email': skipped_without_email,
            'falha_fila': failed_queue,
        }

    message = 'Envio concluido'
    if failed_queue > 0:
        message = 'Envio parcialmente concluido com falhas'

    return True, message, {
        'total_enviado': sent_count,
        'sem_email': skipped_without_email,
        'falha_fila': failed_queue,
    }


def _run_institutional_send_job(job_id, certificate_id, app_obj):
    with app_obj.app_context():
        try:
            _update_send_job(
                job_id,
                status='running',
                message='Gerando PDFs e enfileirando e-mails.',
            )
            success, message, summary = _send_institutional_certificates_sync(certificate_id)
            _update_send_job(
                job_id,
                status='completed' if success else 'error',
                completed=True,
                resultado='sucesso' if success else 'erro',
                message=message,
                **summary,
            )
        except Exception as exc:
            current_app.logger.exception(
                'Falha no job de envio em lote de certificados institucionais (certificate_id=%s)',
                certificate_id,
            )
            _update_send_job(
                job_id,
                status='error',
                completed=True,
                resultado='erro',
                message=f'Falha inesperada no envio: {exc}',
                total_enviado=0,
                sem_email=0,
                falha_fila=0,
            )


def _get_or_create_category(nome):
    normalized = (nome or '').strip()
    if not normalized:
        return None
    existing = InstitutionalCertificateCategory.query.filter(
        InstitutionalCertificateCategory.nome.ilike(normalized)
    ).first()
    if existing:
        return existing
    category = InstitutionalCertificateCategory(nome=normalized)
    db.session.add(category)
    db.session.flush()
    return category


def _resolve_recipient_user(email=None, cpf=None, username_hint=None, metadata=None):
    metadata = metadata if isinstance(metadata, dict) else {}

    normalized_cpf = (cpf or '').strip()
    normalized_email = (email or '').strip().lower()
    normalized_username = (username_hint or metadata.get('username') or '').strip()
    normalized_ra = (metadata.get('ra') or '').strip()

    if normalized_cpf:
        user = User.query.filter_by(cpf=normalized_cpf).first()
        if user:
            return user

    if normalized_email:
        user = User.query.filter(func.lower(User.email) == normalized_email).first()
        if user:
            return user

    if normalized_username:
        user = User.query.filter_by(username=normalized_username).first()
        if user:
            return user

    if normalized_ra:
        user = User.query.filter_by(ra=normalized_ra).first()
        if user:
            return user

    return None


def _get_user_institutional_recipients(user):
    recipient_filters = []
    if user.username:
        recipient_filters.append(InstitutionalCertificateRecipient.user_username == user.username)
    if user.cpf:
        recipient_filters.append(InstitutionalCertificateRecipient.cpf == user.cpf)
    if user.email:
        recipient_filters.append(
            func.lower(InstitutionalCertificateRecipient.email) == user.email.lower()
        )

    if not recipient_filters:
        return []

    return (
        InstitutionalCertificateRecipient.query
        .join(
            InstitutionalCertificate,
            InstitutionalCertificate.id == InstitutionalCertificateRecipient.certificate_id,
        )
        .filter(or_(*recipient_filters))
        .all()
    )


def _build_user_history_payload(user):
    enrollments_with_context = (
        db.session.query(Enrollment, Activity, Event)
        .join(Activity, Enrollment.activity_id == Activity.id)
        .join(Event, Activity.event_id == Event.id)
        .filter(Enrollment.user_cpf == user.cpf)
        .order_by(Activity.data_atv.desc(), Activity.hora_atv.desc(), Enrollment.id.desc())
        .all()
    )

    activities = []
    event_aggregates = {}
    seen_event_hashes = set()

    for enrollment, activity, event in enrollments_with_context:
        is_present = bool(enrollment.presente)
        cert_hash = (enrollment.cert_hash or '').strip() or None
        if cert_hash:
            seen_event_hashes.add(cert_hash)

        event_key = event.id
        aggregate = event_aggregates.get(event_key)
        if not aggregate:
            aggregate = {
                'event_id': event.id,
                'nome': event.nome,
                'tipo': event.tipo,
                'data_inicio': event.data_inicio.isoformat() if event.data_inicio else None,
                'total_activities': 0,
                'present_activities': 0,
                'attended_hours': 0,
                'certificates': 0,
            }
            event_aggregates[event_key] = aggregate

        aggregate['total_activities'] += 1
        if is_present:
            aggregate['present_activities'] += 1
            aggregate['attended_hours'] += activity.carga_horaria or 0
        if cert_hash:
            aggregate['certificates'] += 1

        activities.append({
            'enrollment_id': enrollment.id,
            'event_id': event.id,
            'event_name': event.nome,
            'activity_name': activity.nome,
            'activity_date': activity.data_atv.isoformat() if activity.data_atv else None,
            'activity_time': activity.hora_atv.isoformat() if activity.hora_atv else None,
            'hours': activity.carga_horaria or 0,
            'presente': is_present,
            'certificate_hash': cert_hash,
            'certificate_delivered': bool(enrollment.cert_entregue),
            'certificate_sent_at': enrollment.cert_data_envio.isoformat() if enrollment.cert_data_envio else None,
        })

    events = sorted(
        event_aggregates.values(),
        key=lambda item: (item.get('data_inicio') or '', item.get('event_id') or 0),
        reverse=True,
    )

    institutional_recipients = _get_user_institutional_recipients(user)
    institutional_certificates = []
    seen_institutional_hashes = set()
    for recipient in institutional_recipients:
        cert_hash = (recipient.cert_hash or '').strip() or None
        if cert_hash:
            seen_institutional_hashes.add(cert_hash)

        metadata = _extract_recipient_metadata(recipient)
        cert = recipient.certificate
        institutional_certificates.append({
            'recipient_id': recipient.id,
            'certificate_id': cert.id if cert else None,
            'title': cert.titulo if cert else None,
            'category': cert.categoria if cert else None,
            'issued_at': cert.data_emissao if cert else None,
            'hours': metadata.get('carga_horaria'),
            'course': metadata.get('curso_usuario'),
            'certificate_hash': cert_hash,
            'certificate_delivered': bool(recipient.cert_entregue),
            'certificate_sent_at': recipient.cert_data_envio.isoformat() if recipient.cert_data_envio else None,
        })

    event_certificates = [
        {
            'certificate_type': 'evento',
            'enrollment_id': item['enrollment_id'],
            'event_id': item['event_id'],
            'event_name': item['event_name'],
            'activity_name': item['activity_name'],
            'issued_at': item['activity_date'],
            'hours': item['hours'],
            'certificate_hash': item['certificate_hash'],
            'certificate_delivered': item['certificate_delivered'],
            'certificate_sent_at': item['certificate_sent_at'],
        }
        for item in activities
        if item['certificate_hash']
    ]

    total_event_hours = sum(item.get('hours', 0) for item in activities if item.get('presente'))
    delivered_event_certificates = sum(1 for item in event_certificates if item.get('certificate_delivered'))
    delivered_institutional_certificates = sum(
        1 for item in institutional_certificates if item.get('certificate_delivered')
    )

    return {
        'user': {
            'username': user.username,
            'nome': user.nome,
            'email': user.email,
            'cpf': user.cpf,
            'ra': user.ra,
            'curso': user.curso,
        },
        'summary': {
            'total_events': len(events),
            'total_activities': len(activities),
            'total_present_activities': sum(1 for item in activities if item.get('presente')),
            'total_event_hours': int(total_event_hours)
            if float(total_event_hours).is_integer()
            else round(total_event_hours, 2),
            'total_event_certificates': len(seen_event_hashes),
            'total_institutional_certificates': len(seen_institutional_hashes),
            'total_certificates': len(seen_event_hashes) + len(seen_institutional_hashes),
            'delivered_event_certificates': delivered_event_certificates,
            'delivered_institutional_certificates': delivered_institutional_certificates,
        },
        'events': events,
        'activities': activities,
        'event_certificates': event_certificates,
        'institutional_certificates': institutional_certificates,
    }


@bp.route('/<int:certificate_id>/users/search', methods=['GET'])
@login_required
def search_users_for_recipients(certificate_id):
    cert, error = _get_managed_certificate_or_error(certificate_id)
    if error:
        return error

    query_text = (request.args.get('q') or '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = min(max(request.args.get('per_page', 10, type=int), 1), 50)

    query = User.query.outerjoin(Course, User.course_id == Course.id)
    if query_text:
        like_term = f'%{query_text}%'
        query = query.filter(or_(
            User.username.ilike(like_term),
            User.nome.ilike(like_term),
            User.email.ilike(like_term),
            User.cpf.ilike(like_term),
            User.ra.ilike(like_term),
            Course.nome.ilike(like_term),
        ))

    pagination = query.order_by(User.nome.asc(), User.username.asc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    return jsonify({
        'items': [
            {
                'username': user.username,
                'nome': user.nome,
                'email': user.email,
                'cpf': user.cpf,
                'ra': user.ra,
                'curso': user.curso,
            }
            for user in pagination.items
        ],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
        'query': query_text,
    })


@bp.route('/<int:certificate_id>/users/<username>/history', methods=['GET'])
@login_required
def get_user_history_for_recipients(certificate_id, username):
    cert, error = _get_managed_certificate_or_error(certificate_id)
    if error:
        return error

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'erro': 'Usuario nao encontrado'}), 404

    return jsonify(_build_user_history_payload(user))


@bp.route('', methods=['GET'])
@login_required
def list_institutional_certificates():
    if not _can_view_institutional_certificates():
        return jsonify({'erro': 'Permissao negada'}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    categoria = request.args.get('categoria')
    status = request.args.get('status')
    titulo = (request.args.get('titulo') or '').strip()

    query = InstitutionalCertificate.query
    query = query.join(InstitutionalCertificateCategory, InstitutionalCertificate.category_id == InstitutionalCertificateCategory.id)
    query = _apply_institutional_certificate_view_scope(query)
    if categoria:
        query = query.filter(InstitutionalCertificateCategory.nome.ilike(f'%{categoria}%'))
    if status:
        query = query.filter(InstitutionalCertificate.status == status)
    if titulo:
        query = query.filter(InstitutionalCertificate.titulo.ilike(f'%{titulo}%'))

    pagination = query.order_by(InstitutionalCertificate.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return jsonify({
        'items': [
            _serialize_institutional_certificate_payload(item)
            for item in pagination.items
        ],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
        'filters': {
            'categoria': categoria,
            'status': status,
            'titulo': titulo,
        }
    })


@bp.route('', methods=['POST'])
@login_required
def create_institutional_certificate():
    if current_user.role not in ['admin', 'extensao', 'gestor']:
        return jsonify({'erro': 'Permissao negada'}), 403

    data = request.get_json(silent=True) or {}
    titulo = (data.get('titulo') or '').strip()
    categoria = (data.get('categoria') or '').strip()
    data_emissao = (data.get('data_emissao') or '').strip()

    if not titulo:
        return jsonify({'erro': 'Titulo e obrigatorio'}), 400
    category = _get_or_create_category(categoria)
    if not category:
        return jsonify({'erro': 'Categoria e obrigatoria'}), 400
    if not _parse_date_iso(data_emissao):
        return jsonify({'erro': 'data_emissao deve estar no formato YYYY-MM-DD'}), 400

    bg_path = (data.get('cert_bg_path') or '').strip() or 'file/fundo_padrao.png'
    raw_template = data.get('template')
    if not raw_template:
        raw_template = CertificateService.build_default_template(
            designer_mode='institutional',
            bg=bg_path,
        )

    normalized_template, template_error = _normalize_template(
        json.dumps(raw_template, ensure_ascii=False),
        designer_mode='institutional',
    )
    if template_error:
        return jsonify({'erro': template_error}), 400

    cert = InstitutionalCertificate(
        created_by_username=current_user.username,
        titulo=titulo,
        category_id=category.id,
        descricao=(data.get('descricao') or '').strip() or None,
        data_emissao=data_emissao,
        signer_name=(data.get('signer_name') or '').strip() or None,
        cert_bg_path=bg_path,
        cert_template_json=normalized_template,
        status='RASCUNHO',
    )

    db.session.add(cert)
    db.session.commit()

    return jsonify({'mensagem': 'Certificado institucional criado', 'id': cert.id}), 201


@bp.route('/<int:certificate_id>', methods=['GET'])
@login_required
def get_institutional_certificate(certificate_id):
    cert, error = _get_viewable_certificate_or_error(certificate_id)
    if error:
        return error

    return jsonify(_serialize_institutional_certificate_payload(cert, include_template=True))


@bp.route('/<int:certificate_id>', methods=['PUT'])
@login_required
def update_institutional_certificate(certificate_id):
    cert, error = _get_managed_certificate_or_error(certificate_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}

    titulo = str(data.get('titulo', cert.titulo) or '').strip()
    categoria = str(data.get('categoria', cert.categoria) or '').strip()
    data_emissao = str(data.get('data_emissao', cert.data_emissao) or '').strip()
    status = str(data.get('status', cert.status or 'RASCUNHO') or '').strip().upper()
    descricao = str(data.get('descricao', cert.descricao) or '').strip()
    signer_name = str(data.get('signer_name', cert.signer_name) or '').strip()

    if not titulo:
        return jsonify({'erro': 'Titulo e obrigatorio'}), 400
    category = _get_or_create_category(categoria)
    if not category:
        return jsonify({'erro': 'Categoria e obrigatoria'}), 400
    if not _parse_date_iso(data_emissao):
        return jsonify({'erro': 'data_emissao deve estar no formato YYYY-MM-DD'}), 400
    if status not in ['RASCUNHO', 'ENVIADO', 'ARQUIVADO']:
        return jsonify({'erro': 'Status invalido'}), 400

    cert.titulo = titulo
    cert.category_id = category.id
    cert.data_emissao = data_emissao
    cert.descricao = descricao or None
    cert.signer_name = signer_name or None
    cert.status = status

    db.session.commit()
    return jsonify({'mensagem': 'Certificado institucional atualizado'})


@bp.route('/<int:certificate_id>/setup', methods=['POST'])
@login_required
def setup_institutional_certificate(certificate_id):
    cert, error = _get_managed_certificate_or_error(certificate_id)
    if error:
        return error

    bg_file = request.files.get('background')
    template_json = request.form.get('template')
    remove_bg = request.form.get('remove_bg') == 'true'

    normalized_template, template_error = _normalize_template(template_json, designer_mode='institutional')
    if template_error:
        return jsonify({'erro': template_error}), 400

    bg_path = None
    if remove_bg:
        cert.cert_bg_path = None
    elif bg_file:
        valid_file, file_error = _validate_image_file(bg_file)
        if not valid_file:
            return jsonify({'erro': file_error}), 400

        filename = secure_filename(f'bg_institutional_{certificate_id}_{bg_file.filename}')
        upload_dir = os.path.join(current_app.root_path, 'static', 'certificates', 'backgrounds')
        os.makedirs(upload_dir, exist_ok=True)
        save_path = os.path.join(upload_dir, filename)
        bg_file.save(save_path)
        bg_path = f'certificates/backgrounds/{filename}'
        cert.cert_bg_path = bg_path

    if normalized_template is not None:
        cert.cert_template_json = normalized_template

    db.session.commit()
    return jsonify({
        'mensagem': 'Configuracao de certificado institucional atualizada com sucesso!',
        'bg_url': url_for('static', filename=bg_path) if bg_path else (url_for('static', filename=cert.cert_bg_path) if cert.cert_bg_path else None),
    })


@bp.route('/<int:certificate_id>/preview_layout', methods=['POST'])
@login_required
def preview_layout(certificate_id):
    cert, error = _get_designer_viewable_certificate_or_error(certificate_id)
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    normalized_template, template_error = _normalize_template_payload(
        payload.get('template'),
        designer_mode='institutional',
    )
    if template_error:
        return jsonify({'erro': template_error}), 400

    preview_data = payload.get('preview_data') or {}
    if not isinstance(preview_data, dict):
        return jsonify({'erro': 'preview_data deve ser um objeto'}), 400

    preview_metadata = {
        'carga_horaria': preview_data.get('{{CARGA_HORARIA}}'),
        'curso_usuario': preview_data.get('{{CURSO_USUARIO}}'),
    }
    preview_recipient = SimpleNamespace(
        id=0,
        nome=str(preview_data.get('{{RECIPIENT_NAME}}') or 'Destinatario Preview'),
        email=None,
        cpf=str(preview_data.get('{{CPF}}') or 'PREVIEW-INSTITUTIONAL'),
        cert_hash=str(preview_data.get('{{HASH}}') or 'VALID-SAMPLE-HASH'),
        metadata_json=json.dumps(preview_metadata, ensure_ascii=False),
        linked_user=None,
    )

    pdf_path = institutional_service.generate_recipient_pdf(
        cert,
        preview_recipient,
        template_override=normalized_template,
        tag_overrides=preview_data,
    )
    return _build_pdf_preview_response(pdf_path)


@bp.route('/<int:certificate_id>/upload_asset', methods=['POST'])
@login_required
def upload_institutional_asset(certificate_id):
    cert, error = _get_managed_certificate_or_error(certificate_id)
    if error:
        return error

    image_file = request.files.get('asset')
    valid_file, file_error = _validate_image_file(image_file)
    if not valid_file:
        return jsonify({'erro': file_error}), 400

    filename = secure_filename(f'asset_institutional_{certificate_id}_{image_file.filename}')
    upload_dir = os.path.join(current_app.root_path, 'static', 'certificates', 'assets')
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, filename)
    image_file.save(save_path)

    return jsonify({
        'mensagem': 'Asset enviado com sucesso',
        'asset_url': url_for('static', filename=f'certificates/assets/{filename}'),
        'asset_path': f'certificates/assets/{filename}',
    })


@bp.route('/<int:certificate_id>/duplicate', methods=['POST'])
@login_required
def duplicate_institutional_certificate(certificate_id):
    cert, error = _get_managed_certificate_or_error(certificate_id)
    if error:
        return error

    duplicated = InstitutionalCertificate(
        created_by_username=current_user.username,
        titulo=f"{cert.titulo} (Copia)",
        category_id=cert.category_id,
        descricao=cert.descricao,
        data_emissao=cert.data_emissao,
        signer_name=cert.signer_name,
        cert_bg_path=cert.cert_bg_path,
        cert_template_json=cert.cert_template_json,
        status='RASCUNHO',
    )

    db.session.add(duplicated)
    db.session.flush()

    for r in cert.recipients:
        copied_recipient = InstitutionalCertificateRecipient(
            certificate_id=duplicated.id,
            user_username=r.user_username,
            nome=r.nome,
            email=r.email,
            cpf=r.cpf,
            metadata_json=r.metadata_json,
            cert_hash=institutional_service.build_hash(duplicated.id, r.nome, r.email),
            cert_entregue=False,
            cert_data_envio=None,
        )
        db.session.add(copied_recipient)

    db.session.commit()
    return jsonify({'mensagem': 'Certificado duplicado com sucesso', 'id': duplicated.id}), 201


@bp.route('/<int:certificate_id>', methods=['DELETE'])
@login_required
def delete_institutional_certificate(certificate_id):
    cert, error = _get_deletable_certificate_or_error(certificate_id)
    if error:
        return error

    delete_block_status = _get_institutional_certificate_delete_block_status(cert)
    if delete_block_status['has_linked_records']:
        return jsonify({
            'erro': delete_block_status['delete_block_reason'],
            'linked_recipients_count': delete_block_status['linked_recipients_count'],
        }), 400

    db.session.delete(cert)
    db.session.commit()
    return jsonify({'mensagem': 'Certificado removido com sucesso'})


@bp.route('/<int:certificate_id>/recipients', methods=['GET'])
@login_required
def list_recipients(certificate_id):
    cert, error = _get_viewable_certificate_or_error(certificate_id)
    if error:
        return error

    page = request.args.get('page', 1, type=int)
    per_page = min(max(request.args.get('per_page', 10, type=int), 1), 100)
    query_text = (request.args.get('q') or '').strip()
    sort_by = (request.args.get('sort_by') or 'id').strip().lower()
    sort_dir = (request.args.get('sort_dir') or 'desc').strip().lower()
    descending = sort_dir != 'asc'

    query = _apply_institutional_recipient_view_scope(
        InstitutionalCertificateRecipient.query.filter_by(certificate_id=certificate_id)
    )
    if query_text:
        like_term = f'%{query_text}%'
        query = query.filter(or_(
            InstitutionalCertificateRecipient.nome.ilike(like_term),
            InstitutionalCertificateRecipient.email.ilike(like_term),
            InstitutionalCertificateRecipient.cpf.ilike(like_term),
            InstitutionalCertificateRecipient.metadata_json.ilike(like_term),
        ))

    sortable_columns = {
        'id': InstitutionalCertificateRecipient.id,
        'nome': InstitutionalCertificateRecipient.nome,
        'email': InstitutionalCertificateRecipient.email,
        'cpf': InstitutionalCertificateRecipient.cpf,
        'cert_data_envio': InstitutionalCertificateRecipient.cert_data_envio,
        'cert_entregue': InstitutionalCertificateRecipient.cert_entregue,
    }

    if sort_by in ('carga_horaria', 'curso_usuario'):
        recipients = query.all()

        def sort_key(recipient):
            metadata = _extract_recipient_metadata(recipient)
            if sort_by == 'carga_horaria':
                numeric = _to_float_or_none(metadata.get('carga_horaria'))
                return (numeric is None, numeric if numeric is not None else 0)
            course = str(metadata.get('curso_usuario') or '').lower()
            return (course == '', course)

        recipients.sort(key=sort_key, reverse=descending)
        total = len(recipients)
        start = (page - 1) * per_page
        end = start + per_page
        paged_items = recipients[start:end]
        pages = max((total + per_page - 1) // per_page, 1)
        current_page = min(max(page, 1), pages)
    else:
        order_column = sortable_columns.get(sort_by, InstitutionalCertificateRecipient.id)
        order_clause = order_column.desc() if descending else order_column.asc()
        pagination = query.order_by(order_clause, InstitutionalCertificateRecipient.id.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False,
        )
        paged_items = pagination.items
        total = pagination.total
        pages = pagination.pages
        current_page = pagination.page

    return jsonify({
        'items': [
            {
                'id': r.id,
                'nome': _recipient_effective_profile(r)['nome'],
                'email': _recipient_effective_profile(r)['email'],
                'cpf': _recipient_effective_profile(r)['cpf'],
                'user_username': _recipient_effective_profile(r)['user_username'],
                'linked_user_nome': r.linked_user.nome if r.linked_user else None,
                'carga_horaria': _extract_recipient_metadata(r).get('carga_horaria'),
                'curso_usuario': _extract_recipient_metadata(r).get('curso_usuario'),
                'cert_hash': r.cert_hash,
                'cert_entregue': r.cert_entregue,
                'cert_data_envio': r.cert_data_envio.isoformat() if r.cert_data_envio else None,
            }
            for r in paged_items
        ],
        'total': total,
        'pages': pages,
        'current_page': current_page,
        'query': query_text,
        'sort_by': sort_by,
        'sort_dir': 'desc' if descending else 'asc',
    })


@bp.route('/<int:certificate_id>/recipients', methods=['POST'])
@login_required
def add_recipients(certificate_id):
    cert, error = _get_managed_certificate_or_error(certificate_id)
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    rows = payload.get('recipients') or []
    if not isinstance(rows, list) or not rows:
        return jsonify({'erro': 'Envie recipients como lista nao vazia'}), 400

    inserted = 0
    skipped = 0
    for row in rows:
        nome = (row.get('nome') or '').strip()
        email = (row.get('email') or '').strip().lower() or None
        cpf = (row.get('cpf') or '').strip() or None
        username_hint = (row.get('username') or '').strip() or None
        metadata = row.get('metadata') or {}
        if not isinstance(metadata, dict):
            metadata = {}

        carga_horaria_raw = row.get('carga_horaria', metadata.get('carga_horaria'))
        curso_usuario_raw = row.get('curso_usuario', metadata.get('curso_usuario'))
        carga_horaria = _normalize_workload_hours(carga_horaria_raw)
        curso_usuario = (str(curso_usuario_raw or '').strip() or None)

        linked_user = _resolve_recipient_user(
            email=email,
            cpf=cpf,
            username_hint=username_hint,
            metadata=metadata,
        )
        if linked_user:
            nome = nome or linked_user.nome or linked_user.username
            email = email or (linked_user.email.lower() if linked_user.email else None)
            cpf = cpf or linked_user.cpf
            metadata = {
                **metadata,
                'username': metadata.get('username') or linked_user.username,
                'ra': metadata.get('ra') or linked_user.ra,
            }

        if not nome:
            skipped += 1
            continue
        if email and not _is_valid_email(email):
            skipped += 1
            continue

        exists = None
        if email:
            exists = InstitutionalCertificateRecipient.query.filter_by(
                certificate_id=certificate_id,
                email=email
            ).first()
        if not exists and cpf:
            exists = InstitutionalCertificateRecipient.query.filter_by(
                certificate_id=certificate_id,
                cpf=cpf,
            ).first()
        if exists:
            skipped += 1
            continue

        recipient = InstitutionalCertificateRecipient(
            certificate_id=certificate_id,
            user_username=linked_user.username if linked_user else None,
            nome=nome,
            email=email,
            cpf=cpf,
            metadata_json=json.dumps({
                **metadata,
                'carga_horaria': carga_horaria,
                'curso_usuario': curso_usuario,
            }, ensure_ascii=False),
            cert_hash=institutional_service.build_hash(certificate_id, nome, email),
            cert_entregue=False,
        )
        db.session.add(recipient)
        inserted += 1

    db.session.commit()
    return jsonify({'mensagem': 'Destinatarios processados', 'inserted': inserted, 'skipped': skipped})


@bp.route('/<int:certificate_id>/recipients/import_csv', methods=['POST'])
@login_required
def import_recipients_csv(certificate_id):
    cert, error = _get_managed_certificate_or_error(certificate_id)
    if error:
        return error

    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'erro': 'Arquivo CSV nao enviado'}), 400

    try:
        content = file.read().decode('utf-8-sig')
    except Exception:
        return jsonify({'erro': 'Falha ao ler arquivo CSV'}), 400

    reader = csv.DictReader(io.StringIO(content))
    required_headers = {'nome', 'email', 'cpf'}
    if not reader.fieldnames or not required_headers.issubset(set(h.strip().lower() for h in reader.fieldnames if h)):
        return jsonify({'erro': 'CSV deve conter cabecalhos: nome,email,cpf'}), 400

    inserted = 0
    skipped = 0
    for row in reader:
        normalized = {str(k).strip().lower(): (v or '').strip() for k, v in row.items()}
        nome = normalized.get('nome', '')
        email = normalized.get('email', '').lower() or None
        cpf = normalized.get('cpf', '') or None
        username_hint = normalized.get('username') or None
        carga_horaria = _normalize_workload_hours(normalized.get('carga_horaria'))
        curso_usuario = normalized.get('curso_usuario') or None

        linked_user = _resolve_recipient_user(
            email=email,
            cpf=cpf,
            username_hint=username_hint,
            metadata=normalized,
        )
        if linked_user:
            nome = nome or linked_user.nome or linked_user.username
            email = email or (linked_user.email.lower() if linked_user.email else None)
            cpf = cpf or linked_user.cpf

        if not nome:
            skipped += 1
            continue
        if email and not _is_valid_email(email):
            skipped += 1
            continue

        exists = None
        if email:
            exists = InstitutionalCertificateRecipient.query.filter_by(
                certificate_id=cert.id,
                email=email,
            ).first()
        if not exists and cpf:
            exists = InstitutionalCertificateRecipient.query.filter_by(
                certificate_id=cert.id,
                cpf=cpf,
            ).first()
        if exists:
            skipped += 1
            continue

        recipient = InstitutionalCertificateRecipient(
            certificate_id=cert.id,
            user_username=linked_user.username if linked_user else None,
            nome=nome,
            email=email,
            cpf=cpf,
            metadata_json=json.dumps({
                'username': linked_user.username if linked_user else username_hint,
                'ra': linked_user.ra if linked_user else normalized.get('ra') or None,
                'carga_horaria': carga_horaria,
                'curso_usuario': curso_usuario,
            }, ensure_ascii=False),
            cert_hash=institutional_service.build_hash(cert.id, nome, email),
            cert_entregue=False,
        )
        db.session.add(recipient)
        inserted += 1

    db.session.commit()
    return jsonify({'mensagem': 'Importacao CSV concluida', 'inserted': inserted, 'skipped': skipped})


@bp.route('/<int:certificate_id>/recipients/<int:recipient_id>', methods=['DELETE'])
@login_required
def remove_recipient(certificate_id, recipient_id):
    cert, error = _get_managed_certificate_or_error(certificate_id)
    if error:
        return error

    recipient = InstitutionalCertificateRecipient.query.filter_by(
        id=recipient_id,
        certificate_id=certificate_id,
    ).first()
    if not recipient:
        return jsonify({'erro': 'Destinatario nao encontrado'}), 404

    db.session.delete(recipient)
    db.session.commit()
    return jsonify({'mensagem': 'Destinatario removido'})


@bp.route('/<int:certificate_id>/recipients/<int:recipient_id>', methods=['PUT'])
@login_required
def update_recipient_metadata(certificate_id, recipient_id):
    cert, error = _get_managed_certificate_or_error(certificate_id)
    if error:
        return error

    recipient = InstitutionalCertificateRecipient.query.filter_by(
        id=recipient_id,
        certificate_id=certificate_id,
    ).first()
    if not recipient:
        return jsonify({'erro': 'Destinatario nao encontrado'}), 404

    payload = request.get_json(silent=True) or {}
    carga_horaria = _normalize_workload_hours(payload.get('carga_horaria'))
    curso_usuario = (str(payload.get('curso_usuario') or '').strip() or None)

    metadata = _extract_recipient_metadata(recipient)
    metadata['carga_horaria'] = carga_horaria
    metadata['curso_usuario'] = curso_usuario
    recipient.metadata_json = json.dumps(metadata, ensure_ascii=False)

    db.session.commit()
    return jsonify({
        'mensagem': 'Dados do destinatario atualizados',
        'recipient': {
            'id': recipient.id,
            'carga_horaria': carga_horaria,
            'curso_usuario': curso_usuario,
        }
    })


@bp.route('/<int:certificate_id>/recipients/<int:recipient_id>/resend', methods=['POST'])
@login_required
def resend_recipient(certificate_id, recipient_id):
    cert, error = _get_managed_certificate_or_error(certificate_id)
    if error:
        return error

    recipient = InstitutionalCertificateRecipient.query.filter_by(
        id=recipient_id,
        certificate_id=certificate_id,
    ).first()
    if not recipient:
        return jsonify({'erro': 'Destinatario nao encontrado'}), 404

    profile = _recipient_effective_profile(recipient)

    if not profile['email']:
        return jsonify({'erro': 'Destinatario sem email cadastrado'}), 400

    if not recipient.cert_hash:
        recipient.cert_hash = institutional_service.build_hash(certificate_id, profile['nome'], profile['email'])

    pdf_path = institutional_service.generate_recipient_pdf(cert, recipient)
    queued = institutional_service.queue_email(cert, recipient, pdf_path)
    if not queued:
        return jsonify({'erro': 'Problema no envio: falha ao enfileirar email'}), 500

    recipient.cert_entregue = True
    recipient.cert_data_envio = datetime.utcnow()
    cert.status = 'ENVIADO'
    db.session.commit()

    return jsonify({'mensagem': 'Reenvio enfileirado com sucesso', 'resultado': 'sucesso'})


@bp.route('/<int:certificate_id>/recipients/export_csv', methods=['GET'])
@login_required
def export_recipients_csv(certificate_id):
    cert, error = _get_viewable_certificate_or_error(certificate_id)
    if error:
        return error

    recipients = _apply_institutional_recipient_view_scope(
        InstitutionalCertificateRecipient.query.filter_by(certificate_id=certificate_id)
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['nome', 'email', 'cpf', 'carga_horaria', 'curso_usuario', 'cert_hash', 'cert_entregue', 'cert_data_envio'])

    for r in recipients:
        profile = _recipient_effective_profile(r)
        metadata = _extract_recipient_metadata(r)
        writer.writerow([
            profile['nome'] or '',
            profile['email'] or '',
            profile['cpf'] or '',
            metadata.get('carga_horaria') or '',
            metadata.get('curso_usuario') or '',
            r.cert_hash or '',
            'sim' if r.cert_entregue else 'nao',
            r.cert_data_envio.isoformat() if r.cert_data_envio else '',
        ])

    csv_content = output.getvalue()
    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=institutional_cert_{cert.id}_recipients.csv'
    return response


@bp.route('/<int:certificate_id>/recipients/<int:recipient_id>/download', methods=['GET'])
@login_required
def download_recipient_pdf(certificate_id, recipient_id):
    cert, recipient, error = _get_viewable_recipient_or_error(certificate_id, recipient_id)
    if error:
        return error

    profile = _recipient_effective_profile(recipient)
    if not recipient.cert_hash:
        recipient.cert_hash = institutional_service.build_hash(certificate_id, profile['nome'], profile['email'])
        db.session.commit()

    try:
        pdf_path = institutional_service.generate_recipient_pdf(cert, recipient)
        if not pdf_path:
            return jsonify({'erro': 'Falha ao gerar PDF'}), 500

        filename = f'institutional_{cert.id}_{recipient.id}.pdf'
        return send_file(pdf_path, as_attachment=True, download_name=filename)
    except Exception as exc:
        current_app.logger.exception(
            'Erro ao gerar/baixar PDF institucional (cert_id=%s, recipient_id=%s)',
            certificate_id,
            recipient_id,
        )
        return jsonify({'erro': f'Falha ao gerar PDF institucional: {str(exc)}'}), 500


@bp.route('/download_public/<string:cert_hash>', methods=['GET'])
def download_public_by_hash(cert_hash):
    """Public download endpoint for institutional certificate by certificate hash."""
    recipient = InstitutionalCertificateRecipient.query.filter_by(cert_hash=cert_hash).first()
    if not recipient:
        return jsonify({'erro': 'Certificado nao encontrado'}), 404

    cert = db.session.get(InstitutionalCertificate, recipient.certificate_id)
    if not cert:
        return jsonify({'erro': 'Certificado nao encontrado'}), 404

    profile = _recipient_effective_profile(recipient)
    if not recipient.cert_hash:
        recipient.cert_hash = institutional_service.build_hash(recipient.certificate_id, profile['nome'], profile['email'])
        db.session.commit()

    pdf_path = institutional_service.generate_recipient_pdf(cert, recipient)
    if not pdf_path:
        return jsonify({'erro': 'Falha ao gerar PDF'}), 500

    filename = f'institutional_{cert.id}_{recipient.id}.pdf'
    return send_file(pdf_path, as_attachment=True, download_name=filename)


@bp.route('/preview_public/<string:cert_hash>', methods=['GET'])
def preview_public_by_hash(cert_hash):
    """Public preview endpoint for institutional certificate by certificate hash."""
    recipient = InstitutionalCertificateRecipient.query.filter_by(cert_hash=cert_hash).first()
    if not recipient:
        return jsonify({'erro': 'Certificado nao encontrado'}), 404

    cert = db.session.get(InstitutionalCertificate, recipient.certificate_id)
    if not cert:
        return jsonify({'erro': 'Certificado nao encontrado'}), 404

    profile = _recipient_effective_profile(recipient)
    if not recipient.cert_hash:
        recipient.cert_hash = institutional_service.build_hash(recipient.certificate_id, profile['nome'], profile['email'])
        db.session.commit()

    pdf_path = institutional_service.generate_recipient_pdf(cert, recipient)
    if not pdf_path:
        return jsonify({'erro': 'Falha ao gerar PDF'}), 500

    return _build_pdf_preview_response(pdf_path)


@bp.route('/<int:certificate_id>/recipients/<int:recipient_id>/preview', methods=['GET'])
@login_required
def preview_recipient_pdf(certificate_id, recipient_id):
    cert, recipient, error = _get_viewable_recipient_or_error(certificate_id, recipient_id)
    if error:
        return error

    profile = _recipient_effective_profile(recipient)
    if not recipient.cert_hash:
        recipient.cert_hash = institutional_service.build_hash(certificate_id, profile['nome'], profile['email'])
        db.session.commit()

    pdf_path = institutional_service.generate_recipient_pdf(cert, recipient)
    if not pdf_path:
        return jsonify({'erro': 'Falha ao gerar PDF'}), 500

    return _build_pdf_preview_response(pdf_path)


@bp.route('/<int:certificate_id>/send', methods=['POST'])
@login_required
def send_institutional_certificates(certificate_id):
    cert, error = _get_managed_certificate_or_error(certificate_id)
    if error:
        return error

    with _SEND_CERTIFICATE_LOCK:
        active_job = _get_active_send_job(certificate_id, current_user.username)
        if active_job:
            return jsonify({
                'job_id': active_job['job_id'],
                'mensagem': active_job.get('message') or 'Já existe um envio em processamento.',
                'resultado': 'processando',
                'reused': True,
            }), 202

        job_id = uuid4().hex
        _SEND_CERTIFICATE_JOBS[job_id] = {
            'job_id': job_id,
            'certificate_id': certificate_id,
            'created_by': current_user.username,
            'status': 'queued',
            'completed': False,
            'resultado': 'processando',
            'message': 'Envio institucional iniciado.',
            'total_enviado': 0,
            'sem_email': 0,
            'falha_fila': 0,
            'created_at': time.time(),
            'updated_at': time.time(),
        }

    app_obj = current_app._get_current_object()
    worker = Thread(target=_run_institutional_send_job, args=(job_id, certificate_id, app_obj), daemon=True)
    worker.start()

    return jsonify({
        'job_id': job_id,
        'mensagem': 'Envio institucional iniciado em segundo plano.',
        'resultado': 'processando',
    }), 202


@bp.route('/send/status/<job_id>', methods=['GET'])
@login_required
def institutional_send_status(job_id):
    with _SEND_CERTIFICATE_LOCK:
        job = dict(_SEND_CERTIFICATE_JOBS.get(job_id) or {})

    if not job:
        return jsonify({'erro': 'Job não encontrado.'}), 404

    cert = db.session.get(InstitutionalCertificate, job.get('certificate_id'))
    if not cert or not _can_edit_institutional_certificate(cert):
        return jsonify({'erro': 'Acesso negado.'}), 403

    return jsonify(job)
