from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, abort, url_for, send_file
from flask_login import login_required, current_user
from app.services.certificate_service import CertificateService
from app.services.event_service import EventService
from app.services.event_team_certificate_service import EventTeamCertificateService
from werkzeug.utils import secure_filename
from threading import Lock, Thread
from uuid import uuid4
from types import SimpleNamespace
import os
import json
import re
import time

from sqlalchemy.exc import IntegrityError
from app.models import Event, Enrollment, User, Activity, EventTeamCertificateRecipient
from app.extensions import db
from app.utils import build_absolute_app_url, normalize_cpf

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
MAX_DESIGN_IMAGE_SIZE = 8 * 1024 * 1024

bp = Blueprint('certificates', __name__, url_prefix='/api/certificates')
cert_service = CertificateService()
team_cert_service = EventTeamCertificateService()
_SEND_BATCH_JOBS = {}
_SEND_BATCH_LOCK = Lock()
_SEND_TEAM_BATCH_JOBS = {}
_SEND_TEAM_BATCH_LOCK = Lock()


def _prune_job_cache(jobs, max_completed_age=300, max_entries=100):
    now = time.time()
    to_remove = [job_id for job_id, job in list(jobs.items()) if job.get('completed') and now - job.get('updated_at', 0) > max_completed_age]
    for job_id in to_remove:
        del jobs[job_id]
    if len(jobs) > max_entries:
        sorted_jobs = sorted(jobs.items(), key=lambda x: x[1].get('updated_at', 0))
        for job_id, _ in sorted_jobs[:len(jobs) - max_entries]:
            del jobs[job_id]


def _is_allowed_image(filename):
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_IMAGE_EXTENSIONS


def _validate_image_file(file_storage):
    if not file_storage or not file_storage.filename:
        return False, "Arquivo não enviado"

    if not _is_allowed_image(file_storage.filename):
        return False, "Formato inválido. Use PNG, JPG, JPEG ou WEBP"

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)

    if size <= 0:
        return False, "Arquivo vazio"
    if size > MAX_DESIGN_IMAGE_SIZE:
        return False, "Arquivo excede o limite de 8MB"

    return True, None


def _get_or_404(model, pk):
    entity = db.session.get(model, pk)
    if entity is None:
        abort(404)
    return entity


def _get_active_send_batch_job(event_id, created_by):
    for job in _SEND_BATCH_JOBS.values():
        if job.get('event_id') != event_id:
            continue
        if job.get('created_by') != created_by:
            continue
        if not job.get('completed'):
            return job
    return None


def _update_send_batch_job(job_id, **kwargs):
    with _SEND_BATCH_LOCK:
        job = _SEND_BATCH_JOBS.get(job_id)
        if not job:
            return None
        job.update(kwargs)
        job['updated_at'] = time.time()
        return dict(job)


def _run_send_batch_job(job_id, event_id, app_obj):
    with app_obj.app_context():
        service = CertificateService()
        try:
            _update_send_batch_job(
                job_id,
                status='running',
                message='Gerando PDFs e enfileirando e-mails.',
            )
            success, message, summary = service.queue_event_certificates(event_id)
            _update_send_batch_job(
                job_id,
                status='completed' if success else 'error',
                completed=True,
                resultado='sucesso' if success else 'erro',
                message=message,
                **summary,
            )
        except Exception as exc:
            current_app.logger.exception('Falha no job de envio em lote de certificados (event_id=%s)', event_id)
            _update_send_batch_job(
                job_id,
                status='error',
                completed=True,
                resultado='erro',
                message=f'Falha inesperada no envio: {exc}',
                total_enviado=0,
                sem_email=0,
                falha_fila=0,
            )


def _normalize_template(template_json, designer_mode='event'):
    if template_json is None:
        return None, None

    normalized, error = _normalize_template_payload(template_json, designer_mode=designer_mode)
    if error:
        return None, error
    return json.dumps(normalized, ensure_ascii=False), None


def _normalize_template_payload(template_source, designer_mode='event'):
    if template_source is None:
        return None, None

    parsed = template_source
    if isinstance(template_source, str):
        try:
            parsed = json.loads(template_source)
        except (ValueError, TypeError):
            return None, "Template inválido: JSON malformado"

    if not isinstance(parsed, dict):
        return None, "Template inválido: estrutura esperada é um objeto"

    for element in parsed.get('elements', []):
        if element.get('is_html') and element.get('html_content'):
            element['html_content'] = _sanitize_html_content(element['html_content'])

    return cert_service.normalize_template_payload(parsed, designer_mode=designer_mode), None


def _build_pdf_preview_response(pdf_path):
    from flask import send_file

    response = send_file(pdf_path, mimetype='application/pdf', conditional=False, max_age=0)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


def _can_manage_event(event):
    return EventService.can_manage_event(current_user, event)


def _can_manage_certificates(event):
    return EventService.can_manage_event_certificates(current_user, event)


def _can_view_certificates(event):
    return EventService.can_view_event_certificates(current_user, event)


def _can_access_own_certificate(enrollment):
    if not enrollment or not current_user.is_authenticated:
        return False
    return bool(current_user.cpf and enrollment.user_cpf == current_user.cpf)


def _sanitize_html_content(html_content):
    """Strips dangerous tags and event-handler attributes to prevent XSS."""
    if not html_content or not isinstance(html_content, str):
        return html_content
    # Remove script / iframe / object / embed blocks
    html_content = re.sub(
        r'<(script|iframe|object|embed|frame|frameset|applet|meta|link|style)[^>]*>.*?</\1>',
        '', html_content, flags=re.DOTALL | re.IGNORECASE
    )
    # Remove self-closing dangerous tags
    html_content = re.sub(
        r'<(script|iframe|meta|link|style|base)[^>]*/?>',
        '', html_content, flags=re.IGNORECASE
    )
    # Remove inline event handlers (on<event>="..." / on<event>='...')
    html_content = re.sub(r'\s+on\w+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)',
                          '', html_content, flags=re.IGNORECASE)
    # Remove javascript: / data: URIs from href/src attributes
    html_content = re.sub(r'(href|src)\s*=\s*["\']?\s*(javascript|data):[^"\'>\s]*["\']?',
                          '', html_content, flags=re.IGNORECASE)
    return html_content


def _is_valid_email(email):
    if not email:
        return False
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def _event_from_enrollment(enrollment):
    if not enrollment:
        return None
    activity = db.session.get(Activity, enrollment.activity_id)
    if not activity:
        return None
    return db.session.get(Event, activity.event_id)


def _certificate_context_for_enrollment(event, enrollment, user):
    """Returns certificate hours/activity context.

    For PADRAO events, certificates are activity-specific (per enrollment).
    For other event types, hours can be aggregated across present activities.
    """
    activity = db.session.get(Activity, enrollment.activity_id) if enrollment else None
    activity_name = activity.nome if activity else ''

    if getattr(event, 'tipo', None) == 'PADRAO' and activity is not None:
        return {
            'hours': activity.carga_horaria or 0,
            'activity': activity,
            'activity_name': activity_name,
        }

    total_hours = 0
    presences = Enrollment.query.join(Activity, Enrollment.activity_id == Activity.id).filter(
        Activity.event_id == event.id,
        Enrollment.user_cpf == user.cpf,
        Enrollment.presente == True,
    ).all()
    for p in presences:
        atv = db.session.get(Activity, p.activity_id)
        if atv:
            total_hours += (atv.carga_horaria or 0)

    return {
        'hours': total_hours,
        'activity': activity,
        'activity_name': activity_name,
    }


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


def _team_recipient_identity_key(nome, email, cpf):
    if cpf:
        return ('cpf', cpf)
    if email:
        return ('email', email)
    return ('nome', (nome or '').strip().lower())


def _find_team_recipient_duplicate(event_id, exclude_id, nome, email, cpf, role_label, activity_id):
    key_type, key_value = _team_recipient_identity_key(nome, email, cpf)
    base_q = EventTeamCertificateRecipient.query.filter_by(
        event_id=event_id, role_label=role_label, source='manual',
    ).filter(EventTeamCertificateRecipient.activity_id == activity_id)
    if key_type == 'cpf':
        candidate = base_q.filter_by(cpf=key_value).first()
    elif key_type == 'email':
        candidate = base_q.filter_by(email=key_value).first()
    else:
        candidate = base_q.filter(db.func.lower(EventTeamCertificateRecipient.nome) == key_value).first()
    if candidate and (exclude_id is None or candidate.id != exclude_id):
        return candidate
    return None


def _team_recipient_values_from_payload(event, payload):
    payload = payload or {}
    nome = str(payload.get('nome') or '').strip()
    role_label = str(payload.get('role_label') or '').strip()
    email = str(payload.get('email') or '').strip().lower() or None
    cpf_raw = payload.get('cpf') if payload.get('cpf') is not None and str(payload.get('cpf')).strip() else None
    cpf = normalize_cpf(cpf_raw) if cpf_raw else None

    raw_id = payload.get('activity_id')
    if raw_id is None or str(raw_id).strip() == '':
        activity_id = None
    else:
        try:
            activity_id = int(raw_id)
        except (ValueError, TypeError):
            return None, 'ID da atividade inválido.'
        if activity_id <= 0:
            return None, 'ID da atividade inválido.'

    workload_hours = team_cert_service.normalize_workload_hours(payload.get('workload_hours'))

    if not nome:
        return None, 'Nome é obrigatório.'
    if not role_label:
        return None, 'Papel é obrigatório.'
    if email and not _is_valid_email(email):
        return None, 'E-mail inválido.'
    if cpf is not None and (not cpf or len(cpf) != 11):
        return None, 'CPF inválido.'
    if activity_id is not None:
        activity = db.session.get(Activity, activity_id)
        if not activity or activity.event_id != event.id:
            return None, 'Atividade não pertence a este evento.'

    return {
        'nome': nome,
        'role_label': role_label,
        'email': email,
        'cpf': cpf,
        'activity_id': activity_id,
        'workload_hours': workload_hours,
    }, None


@bp.route('/setup/<int:event_id>', methods=['POST'])
@login_required
def setup_certificate(event_id):
    """
    Configures the certificate background and template for an event.
    Expects a background image file and a template JSON string.
    """
    event = _get_or_404(Event, event_id)
    if not _can_manage_certificates(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    bg_file = request.files.get('background')
    template_json = request.form.get('template')
    remove_bg = request.form.get('remove_bg') == 'true'

    normalized_template, template_error = _normalize_template(template_json, designer_mode='event')
    if template_error:
        return jsonify({"erro": template_error}), 400
    
    bg_path = None
    if remove_bg:
        bg_path = "" # Explicitly clear in service
    elif bg_file:
        valid_file, file_error = _validate_image_file(bg_file)
        if not valid_file:
            return jsonify({"erro": file_error}), 400

        filename = secure_filename(f"bg_event_{event_id}_{bg_file.filename}")
        upload_dir = os.path.join(current_app.root_path, 'static', 'certificates', 'backgrounds')
        os.makedirs(upload_dir, exist_ok=True)
        save_path = os.path.join(upload_dir, filename)
        bg_file.save(save_path)
        # Store as relative path for web access
        bg_path = f"certificates/backgrounds/{filename}"
    
    success = cert_service.update_config(event_id, bg_path, normalized_template)
    
    if success:
        return jsonify({
            "mensagem": "Configuração de certificado atualizada com sucesso!",
            "bg_url": url_for('static', filename=bg_path) if bg_path else None
        })
    return jsonify({"erro": "Falha ao atualizar configuração"}), 400


@bp.route('/preview_layout/<int:event_id>', methods=['POST'])
@login_required
def preview_layout(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_view_certificates(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    payload = request.get_json(silent=True) or {}
    normalized_template, template_error = _normalize_template_payload(payload.get('template'), designer_mode='event')
    if template_error:
        return jsonify({"erro": template_error}), 400

    preview_data = payload.get('preview_data') or {}
    if not isinstance(preview_data, dict):
        return jsonify({"erro": "preview_data deve ser um objeto"}), 400

    preview_user = SimpleNamespace(
        id=f"preview-event-{event_id}",
        nome=str(preview_data.get('{{NOME}}') or 'Participante Preview'),
        cpf=str(preview_data.get('{{CPF}}') or f'PREVIEW-EVENT-{event_id}'),
        email=None,
    )
    pdf_path = cert_service.generate_pdf(
        event,
        preview_user,
        [],
        preview_data.get('{{HORAS}}') or '0',
        template_override=normalized_template,
        tag_overrides=preview_data,
    )
    return _build_pdf_preview_response(pdf_path)


@bp.route('/upload_asset/<int:event_id>', methods=['POST'])
@login_required
def upload_asset(event_id):
    """Uploads an image asset for inline certificate elements."""
    event = _get_or_404(Event, event_id)
    if not _can_manage_certificates(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    image_file = request.files.get('asset')
    valid_file, file_error = _validate_image_file(image_file)
    if not valid_file:
        return jsonify({"erro": file_error}), 400

    filename = secure_filename(f"asset_event_{event_id}_{image_file.filename}")
    upload_dir = os.path.join(current_app.root_path, 'static', 'certificates', 'assets')
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, filename)
    image_file.save(save_path)

    return jsonify({
        "mensagem": "Asset enviado com sucesso",
        "asset_url": url_for('static', filename=f"certificates/assets/{filename}"),
        "asset_path": f"certificates/assets/{filename}"
    })

@bp.route('/send_batch/<int:event_id>', methods=['POST'])
@login_required
def send_batch(event_id):
    """Triggers the mass generation and queued delivery of certificates."""
    event = _get_or_404(Event, event_id)
    if not _can_manage_certificates(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    with _SEND_BATCH_LOCK:
        active_job = _get_active_send_batch_job(event_id, current_user.username)
        if active_job:
            return jsonify({
                'job_id': active_job['job_id'],
                'mensagem': active_job.get('message') or 'Já existe um envio em processamento.',
                'resultado': 'processando',
                'reused': True,
            }), 202

        job_id = uuid4().hex
        _SEND_BATCH_JOBS[job_id] = {
            'job_id': job_id,
            'event_id': event_id,
            'created_by': current_user.username,
            'status': 'queued',
            'completed': False,
            'resultado': 'processando',
            'message': 'Envio em lote iniciado.',
            'total_enviado': 0,
            'sem_email': 0,
            'falha_fila': 0,
            'created_at': time.time(),
            'updated_at': time.time(),
        }
        _prune_job_cache(_SEND_BATCH_JOBS)

    app_obj = current_app._get_current_object()
    worker = Thread(target=_run_send_batch_job, args=(job_id, event_id, app_obj), daemon=True)
    worker.start()

    return jsonify({
        'job_id': job_id,
        'mensagem': 'Envio em lote iniciado em segundo plano.',
        'resultado': 'processando',
    }), 202


@bp.route('/send_batch/status/<job_id>', methods=['GET'])
@login_required
def send_batch_status(job_id):
    with _SEND_BATCH_LOCK:
        job = dict(_SEND_BATCH_JOBS.get(job_id) or {})

    if not job:
        return jsonify({'erro': 'Job não encontrado.'}), 404

    event = db.session.get(Event, job.get('event_id'))
    if not event or not _can_manage_certificates(event):
        return jsonify({'erro': 'Acesso negado.'}), 403

    return jsonify(job)

@bp.route('/list_delivery/<int:event_id>', methods=['GET'])
@login_required
def list_delivery(event_id):
    """Lists all participants eligible for certificates with pagination."""
    event = _get_or_404(Event, event_id)
    if not _can_view_certificates(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    pagination = Enrollment.query.join(Activity, Enrollment.activity_id == Activity.id).filter(
        Activity.event_id == event_id,
        Enrollment.presente == True,
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    res = []
    for e in pagination.items:
        user = User.query.filter_by(cpf=e.user_cpf).first()
        activity = db.session.get(Activity, e.activity_id)
        res.append({
            "enrollment_id": e.id,
            "nome": e.nome,
            "cpf": e.user_cpf,
            "atividade": activity.nome if activity else "-",
            "palestrante": (activity.primary_speaker_name if activity and activity.primary_speaker_name else "-"),
            "palestrantes_label": (activity.palestrantes_label if activity and activity.palestrantes_label else "-"),
            "palestrantes": activity.get_speakers_payload(include_emails=True) if activity else [],
            "email_original": user.email if user else "N/A",
            "email_atual": e.cert_email_alternativo or (user.email if user else ""),
            "entregue": e.cert_entregue,
            "data_envio": e.cert_data_envio.strftime('%d/%m/%Y %H:%M') if e.cert_data_envio else "Pendente",
            "hash": e.cert_hash
        })
    
    return jsonify({
        "items": res,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })

@bp.route('/update_email/<int:enrollment_id>', methods=['POST'])
@login_required
def update_email(enrollment_id):
    """Updates the target email for a specific certificate delivery."""
    new_email = request.json.get('email')
    if not _is_valid_email(new_email):
        return jsonify({"erro": "E-mail inválido"}), 400

    enrollment = _get_or_404(Enrollment, enrollment_id)
    event = _event_from_enrollment(enrollment)
    if not _can_manage_certificates(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    enrollment.cert_email_alternativo = new_email
    db.session.commit()
    return jsonify({"mensagem": "E-mail atualizado!"})

@bp.route('/resend_single/<int:enrollment_id>', methods=['POST'])
@login_required
def resend_single(enrollment_id):
    """Triggers a resend for a single certificate."""
    enrollment = _get_or_404(Enrollment, enrollment_id)
    event = _event_from_enrollment(enrollment)
    if not _can_manage_certificates(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    
    if not user: return jsonify({"erro": "Usuário não encontrado"}), 404
    
    cert_ctx = _certificate_context_for_enrollment(event, enrollment, user)
    cert_hours = cert_ctx['hours']
    cert_activity = cert_ctx['activity']
    activity_suffix = f" - {cert_ctx['activity_name']}" if getattr(event, 'tipo', None) == 'PADRAO' and cert_ctx['activity_name'] else ''

    target_email = enrollment.cert_email_alternativo or user.email
    if not target_email: return jsonify({"erro": "E-mail não definido"}), 400

    # Generate and Queue
    pdf_path = cert_service.generate_pdf(event, user, [cert_activity] if cert_activity else [], cert_hours, enrollment=enrollment)
    validation_url = build_absolute_app_url(f"/validar/{enrollment.cert_hash}") if enrollment.cert_hash else ''
    download_url = build_absolute_app_url(f"/api/certificates/download_public/{enrollment.cert_hash}") if enrollment.cert_hash else ''
    event_date = event.data_inicio.strftime('%d/%m/%Y') if event and event.data_inicio else ''
    cert_service.notifier.send_email_task(
        to_email=target_email,
        subject=f"Reenvio de Certificado: {event.nome}{activity_suffix}",
        template_name='certificate_ready.html',
        template_data={
            'user_name': user.nome,
            'event_name': event.nome,
            'event_date': event_date,
            'course_hours': cert_hours,
            'certificate_number': enrollment.cert_hash,
            'certificate_download_url': download_url,
            'view_certificate_url': build_absolute_app_url(f"/api/certificates/preview_public/{enrollment.cert_hash}") if enrollment.cert_hash else '',
            'my_certificates_url': validation_url,
        },
        attachment_path=pdf_path
    )
    
    from datetime import datetime
    enrollment.cert_data_envio = datetime.now()
    enrollment.cert_entregue = True # Mark as initiated
    db.session.commit()
    
    return jsonify({"mensagem": "Reenvio solicitado!"})


@bp.route('/download_public/<string:cert_hash>')
def download_public(cert_hash):
    """Public download endpoint for event certificates using certificate hash."""
    enrollment = Enrollment.query.filter_by(cert_hash=cert_hash).first()
    if not enrollment:
        return "Certificado não encontrado", 404

    event = _event_from_enrollment(enrollment)
    if not event:
        return "Evento não encontrado", 404

    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    if not user:
        return "Usuário não encontrado", 404

    cert_ctx = _certificate_context_for_enrollment(event, enrollment, user)

    from flask import send_file
    pdf_path = cert_service.generate_pdf(event, user, [cert_ctx['activity']] if cert_ctx['activity'] else [], cert_ctx['hours'], enrollment=enrollment)
    filename = f"Certificado_{user.nome.replace(' ', '_')}.pdf"
    return send_file(pdf_path, as_attachment=True, download_name=filename)


@bp.route('/preview_public/<string:cert_hash>')
def preview_public(cert_hash):
    """Public preview endpoint for event certificates using certificate hash."""
    enrollment = Enrollment.query.filter_by(cert_hash=cert_hash).first()
    if not enrollment:
        return "Certificado não encontrado", 404

    event = _event_from_enrollment(enrollment)
    if not event:
        return "Evento não encontrado", 404

    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    if not user:
        return "Usuário não encontrado", 404

    cert_ctx = _certificate_context_for_enrollment(event, enrollment, user)

    pdf_path = cert_service.generate_pdf(event, user, [cert_ctx['activity']] if cert_ctx['activity'] else [], cert_ctx['hours'], enrollment=enrollment)
    return _build_pdf_preview_response(pdf_path)

@bp.route('/download/<int:enrollment_id>')
@login_required
def download_single(enrollment_id):
    # ... (Keep existing download_single code)
    enrollment = _get_or_404(Enrollment, enrollment_id)
    event = _event_from_enrollment(enrollment)
    if not (_can_view_certificates(event) or _can_access_own_certificate(enrollment)):
        return "Acesso negado", 403

    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    if not user: return "Usuário não encontrado", 404
    cert_ctx = _certificate_context_for_enrollment(event, enrollment, user)
    from flask import send_file
    pdf_path = cert_service.generate_pdf(event, user, [cert_ctx['activity']] if cert_ctx['activity'] else [], cert_ctx['hours'], enrollment=enrollment)
    return send_file(pdf_path, as_attachment=True, download_name=f"Certificado_{user.nome.replace(' ', '_')}.pdf")

@bp.route('/preview/<int:enrollment_id>')
@login_required
def preview_single(enrollment_id):
    """Generates and serves a certificate PDF for inline viewing (preview)."""
    enrollment = _get_or_404(Enrollment, enrollment_id)
    event = _event_from_enrollment(enrollment)
    if not (_can_view_certificates(event) or _can_access_own_certificate(enrollment)):
        return "Acesso negado", 403

    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    
    if not user: return "Usuário não encontrado", 404
    
    cert_ctx = _certificate_context_for_enrollment(event, enrollment, user)

    pdf_path = cert_service.generate_pdf(event, user, [cert_ctx['activity']] if cert_ctx['activity'] else [], cert_ctx['hours'], enrollment=enrollment)
    return _build_pdf_preview_response(pdf_path)


@bp.route('/bootstrap/<int:event_id>', methods=['GET'])
@login_required
def designer_bootstrap(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_view_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403

    bootstrap = cert_service.build_designer_bootstrap(event, designer_mode='event')
    bootstrap['can_manage_certificates'] = _can_manage_certificates(event)
    bootstrap['can_view_certificates'] = _can_view_certificates(event)
    bootstrap['recipient_scope'] = 'event_participants'
    return jsonify(bootstrap)


@bp.route('/team/event/<int:event_id>/bootstrap', methods=['GET'])
@login_required
def team_designer_bootstrap(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_view_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403

    bootstrap = cert_service.build_designer_bootstrap(event, designer_mode='team_event')
    bootstrap['can_manage_certificates'] = _can_manage_certificates(event)
    bootstrap['can_view_certificates'] = _can_view_certificates(event)
    bootstrap['recipient_scope'] = 'event_team_resolved'
    return jsonify(bootstrap)


@bp.route('/team/event/<int:event_id>/recipients', methods=['GET'])
@login_required
def list_team_recipients(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_view_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    resolved = team_cert_service.resolve_event_recipients(event)
    items = []
    for row in resolved:
        items.append({
            'id': row.get('id'),
            'nome': row['nome'],
            'email': row.get('email'),
            'cpf': row.get('cpf'),
            'role_label': row['role_label'],
            'activity_id': row.get('activity_id'),
            'activity_name': row.get('activity_name'),
            'workload_hours': row.get('workload_hours'),
            'source': row['source'],
            'resolved_key': row['resolved_key'],
            'cert_hash': row.get('cert_hash'),
            'cert_entregue': row.get('cert_entregue', False),
            'cert_data_envio': row.get('cert_data_envio'),
        })
    return jsonify({'items': items, 'total': len(items)})


@bp.route('/team/event/<int:event_id>/sync', methods=['POST'])
@login_required
def sync_team_recipients(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_manage_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    try:
        summary = team_cert_service.sync_event_recipients(event)
    except IntegrityError:
        db.session.rollback()
        return jsonify({'erro': 'Falha ao sincronizar destinatários. Tente novamente.'}), 409
    return jsonify({'mensagem': 'Destinatários sincronizados.', **summary})


@bp.route('/team/event/<int:event_id>/recipients', methods=['POST'])
@login_required
def create_team_recipient(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_manage_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    values, error = _team_recipient_values_from_payload(event, request.get_json(silent=True))
    if error:
        return jsonify({'erro': error}), 400
    if _find_team_recipient_duplicate(event.id, None, values['nome'], values['email'], values['cpf'], values['role_label'], values['activity_id']):
        return jsonify({'erro': 'Já existe um destinatário manual para esta pessoa neste evento com o mesmo papel e atividade.'}), 400
    recipient = EventTeamCertificateRecipient(
        event_id=event.id,
        activity_id=values['activity_id'],
        nome=values['nome'],
        email=values['email'],
        cpf=values['cpf'],
        role_label=values['role_label'],
        workload_hours=values['workload_hours'],
        source='manual',
    )
    db.session.add(recipient)
    db.session.commit()
    return jsonify({'mensagem': 'Destinatário criado.', 'recipient': _team_recipient_payload(recipient)}), 201


@bp.route('/team/recipients/<int:recipient_id>', methods=['PUT'])
@login_required
def update_team_recipient(recipient_id):
    recipient = _get_team_recipient_or_404(recipient_id)
    event = _event_for_team_recipient(recipient)
    if not event or not _can_manage_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    values, error = _team_recipient_values_from_payload(event, request.get_json(silent=True))
    if error:
        return jsonify({'erro': error}), 400
    dup = _find_team_recipient_duplicate(event.id, recipient.id, values['nome'], values['email'], values['cpf'], values['role_label'], values['activity_id'])
    if dup:
        return jsonify({'erro': 'Já existe outro destinatário manual para esta pessoa neste evento com o mesmo papel e atividade.'}), 400
    recipient.nome = values['nome']
    recipient.role_label = values['role_label']
    recipient.email = values['email']
    recipient.cpf = values['cpf']
    recipient.activity_id = values['activity_id']
    recipient.workload_hours = values['workload_hours']
    db.session.commit()
    return jsonify({'mensagem': 'Destinatário atualizado.', 'recipient': _team_recipient_payload(recipient)})


@bp.route('/team/recipients/<int:recipient_id>', methods=['DELETE'])
@login_required
def delete_team_recipient(recipient_id):
    recipient = _get_team_recipient_or_404(recipient_id)
    event = _event_for_team_recipient(recipient)
    if not event or not _can_manage_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    db.session.delete(recipient)
    db.session.commit()
    return jsonify({'mensagem': 'Destinatário removido.'})


@bp.route('/team/recipients/<int:recipient_id>/preview', methods=['GET'])
@login_required
def preview_team_recipient(recipient_id):
    recipient = _get_team_recipient_or_404(recipient_id)
    event = _event_for_team_recipient(recipient)
    if not event or not _can_view_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    pdf_path = team_cert_service.generate_recipient_pdf(event, recipient)
    return _build_pdf_preview_response(pdf_path)


@bp.route('/team/recipients/<int:recipient_id>/download', methods=['GET'])
@login_required
def download_team_recipient(recipient_id):
    recipient = _get_team_recipient_or_404(recipient_id)
    event = _event_for_team_recipient(recipient)
    if not event or not _can_view_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    pdf_path = team_cert_service.generate_recipient_pdf(event, recipient)
    filename = f"Certificado_Equipe_{recipient.nome.replace(' ', '_')}.pdf"
    return send_file(pdf_path, as_attachment=True, download_name=filename)


@bp.route('/team/recipients/<int:recipient_id>/resend', methods=['POST'])
@login_required
def resend_team_recipient(recipient_id):
    recipient = _get_team_recipient_or_404(recipient_id)
    event = _event_for_team_recipient(recipient)
    if not event or not _can_manage_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403
    if not recipient.email:
        return jsonify({'erro': 'E-mail não definido para este destinatário.'}), 400
    pdf_path = team_cert_service.generate_recipient_pdf(event, recipient)
    team_cert_service.queue_email(event, recipient, pdf_path)
    recipient.cert_entregue = True
    recipient.cert_data_envio = datetime.now()
    db.session.commit()
    return jsonify({'mensagem': 'Reenvio solicitado.'})


@bp.route('/team/resolved/<path:resolved_key>/preview', methods=['GET'])
@login_required
def preview_team_resolved(resolved_key):
    return _handle_team_resolved_action(resolved_key, 'preview')


@bp.route('/team/resolved/<path:resolved_key>/download', methods=['GET'])
@login_required
def download_team_resolved(resolved_key):
    return _handle_team_resolved_action(resolved_key, 'download')


@bp.route('/team/resolved/<path:resolved_key>/resend', methods=['POST'])
@login_required
def resend_team_resolved(resolved_key):
    return _handle_team_resolved_action(resolved_key, 'resend')


def _event_id_from_resolved_key(resolved_key):
    try:
        _, event_id, _ = str(resolved_key or '').split('|', 2)
        return int(event_id)
    except (TypeError, ValueError):
        abort(404, description='Destinatario resolvido nao encontrado para esta chave.')


def _handle_team_resolved_action(resolved_key, action):
    event_id = _event_id_from_resolved_key(resolved_key)
    event = db.session.get(Event, event_id)
    row = None
    if event:
        for candidate in team_cert_service.resolve_event_recipients(event):
            if candidate.get('resolved_key') == resolved_key:
                row = candidate
                break

    if not event or not row:
        abort(404, description='Destinatario resolvido nao encontrado para esta chave.')

    if not _can_view_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403

    recipient = team_cert_service.build_virtual_recipient(event, row)

    if action == 'preview':
        pdf_path = team_cert_service.generate_recipient_pdf(event, recipient)
        return _build_pdf_preview_response(pdf_path)
    elif action == 'download':
        pdf_path = team_cert_service.generate_recipient_pdf(event, recipient)
        filename = f"Certificado_Equipe_{recipient.nome.replace(' ', '_')}.pdf"
        return send_file(pdf_path, as_attachment=True, download_name=filename)
    elif action == 'resend':
        if not _can_manage_certificates(event):
            return jsonify({'erro': 'Acesso negado para este evento'}), 403
        if not recipient.email:
            return jsonify({'erro': 'E-mail nao definido para este destinatario.'}), 400
        row = team_cert_service.ensure_persisted_automatic_recipient(event, row)
        team_cert_service.ensure_recipient_hash(event.id, row)
        recipient = team_cert_service.build_virtual_recipient(event, row)
        pdf_path = team_cert_service.generate_recipient_pdf(event, recipient)
        team_cert_service.queue_email(event, recipient, pdf_path)
        resolved_id = row.get('id')
        if resolved_id is not None:
            persisted = db.session.get(EventTeamCertificateRecipient, resolved_id)
            if persisted:
                persisted.cert_entregue = True
                persisted.cert_data_envio = datetime.now()
                db.session.commit()
        return jsonify({'mensagem': 'Reenvio solicitado.'})
    else:
        abort(400)


def _run_send_team_batch_job(job_id, event_id, app_obj):
    with app_obj.app_context():
        try:
            _update_send_team_batch_job(
                job_id,
                status='running',
                message='Gerando PDFs e enfileirando e-mails de equipe.',
            )
            event = db.session.get(Event, event_id)
            if not event:
                _update_send_team_batch_job(
                    job_id,
                    status='error',
                    completed=True,
                    resultado='erro',
                    message='Evento nao encontrado.',
                    total_enviado=0,
                    sem_email=0,
                    falha_fila=0,
                )
                return

            resolved_rows = team_cert_service.resolve_event_recipients(event)
            total_enviado = 0
            sem_email = 0
            falha_fila = 0

            missing_hashes = [r for r in resolved_rows if not r.get('cert_hash')]
            if missing_hashes:
                for r in missing_hashes:
                    r = team_cert_service.ensure_persisted_automatic_recipient(event, r)
                    team_cert_service.ensure_recipient_hash(event_id, r)
                db.session.commit()

            for row in resolved_rows:
                if not row.get('email'):
                    sem_email += 1
                    continue

                row = team_cert_service.ensure_persisted_automatic_recipient(event, row)

                recipient = team_cert_service.build_virtual_recipient(event, row)
                try:
                    pdf_path = team_cert_service.generate_recipient_pdf(event, recipient)
                    if not team_cert_service.queue_email(event, recipient, pdf_path):
                        falha_fila += 1
                        continue
                    resolved_id = row.get('id')
                    if resolved_id is not None:
                        persisted_rec = db.session.get(EventTeamCertificateRecipient, resolved_id)
                        if persisted_rec:
                            persisted_rec.cert_entregue = True
                            persisted_rec.cert_data_envio = datetime.now()
                    total_enviado += 1
                except Exception:
                    falha_fila += 1

            db.session.commit()
            _update_send_team_batch_job(
                job_id,
                status='completed',
                completed=True,
                resultado='sucesso',
                message='Envio em lote de equipe concluído.',
                total_enviado=total_enviado,
                sem_email=sem_email,
                falha_fila=falha_fila,
            )
        except Exception as exc:
            current_app.logger.exception('Falha no job de envio em lote de equipe (event_id=%s)', event_id)
            _update_send_team_batch_job(
                job_id,
                status='error',
                completed=True,
                resultado='erro',
                message=f'Falha inesperada no envio de equipe: {exc}',
                total_enviado=0,
                sem_email=0,
                falha_fila=0,
            )


def _update_send_team_batch_job(job_id, **kwargs):
    with _SEND_TEAM_BATCH_LOCK:
        job = _SEND_TEAM_BATCH_JOBS.get(job_id)
        if not job:
            return None
        job.update(kwargs)
        job['updated_at'] = time.time()
        return dict(job)


def _get_active_send_team_batch_job(event_id, created_by):
    for job in _SEND_TEAM_BATCH_JOBS.values():
        if job.get('event_id') != event_id:
            continue
        if job.get('created_by') != created_by:
            continue
        if not job.get('completed'):
            return job
    return None


@bp.route('/team/event/<int:event_id>/send_batch', methods=['POST'])
@login_required
def send_team_batch(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_manage_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403

    with _SEND_TEAM_BATCH_LOCK:
        active_job = _get_active_send_team_batch_job(event_id, current_user.username)
        if active_job:
            return jsonify({
                'job_id': active_job['job_id'],
                'mensagem': active_job.get('message') or 'Já existe um envio em processamento.',
                'resultado': 'processando',
                'reused': True,
            }), 202

        job_id = uuid4().hex
        _SEND_TEAM_BATCH_JOBS[job_id] = {
            'job_id': job_id,
            'event_id': event_id,
            'created_by': current_user.username,
            'status': 'queued',
            'completed': False,
            'resultado': 'processando',
            'message': 'Envio em lote de equipe iniciado.',
            'total_enviado': 0,
            'sem_email': 0,
            'falha_fila': 0,
            'created_at': time.time(),
            'updated_at': time.time(),
        }
        _prune_job_cache(_SEND_TEAM_BATCH_JOBS)

    app_obj = current_app._get_current_object()
    worker = Thread(target=_run_send_team_batch_job, args=(job_id, event_id, app_obj), daemon=True)
    worker.start()

    return jsonify({
        'job_id': job_id,
        'mensagem': 'Envio em lote de equipe iniciado em segundo plano.',
        'resultado': 'processando',
    }), 202


@bp.route('/team/send_batch/status/<job_id>', methods=['GET'])
@login_required
def send_team_batch_status(job_id):
    with _SEND_TEAM_BATCH_LOCK:
        job = dict(_SEND_TEAM_BATCH_JOBS.get(job_id) or {})

    if not job:
        return jsonify({'erro': 'Job não encontrado.'}), 404

    event = db.session.get(Event, job.get('event_id'))
    if not event or not _can_manage_certificates(event):
        return jsonify({'erro': 'Acesso negado.'}), 403

    return jsonify(job)


@bp.route('/team/event/<int:event_id>/setup', methods=['POST'])
@login_required
def setup_team_certificate(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_manage_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403

    bg_file = request.files.get('background')
    template_json = request.form.get('template')
    remove_bg = request.form.get('remove_bg') == 'true'

    normalized_template, template_error = _normalize_template(template_json, designer_mode='team_event')
    if template_error:
        return jsonify({'erro': template_error}), 400

    if normalized_template is None:
        normalized_template = json.dumps(
            team_cert_service.build_default_team_template(event), ensure_ascii=False
        )

    bg_path = event.cert_team_bg_path
    if remove_bg:
        bg_path = ''
    elif bg_file:
        valid_file, file_error = _validate_image_file(bg_file)
        if not valid_file:
            return jsonify({'erro': file_error}), 400

        filename = secure_filename(f"bg_team_event_{event_id}_{bg_file.filename}")
        upload_dir = os.path.join(current_app.root_path, 'static', 'certificates', 'backgrounds')
        os.makedirs(upload_dir, exist_ok=True)
        save_path = os.path.join(upload_dir, filename)
        bg_file.save(save_path)
        bg_path = f"certificates/backgrounds/{filename}"

    event.cert_team_bg_path = bg_path or None
    event.cert_team_template_json = normalized_template
    db.session.commit()

    return jsonify({
        'mensagem': 'Configuracao de certificado de equipe atualizada com sucesso!',
        'bg_url': url_for('static', filename=bg_path) if bg_path else None,
    })


@bp.route('/team/event/<int:event_id>/preview_layout', methods=['POST'])
@login_required
def preview_team_layout(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_view_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403

    payload = request.get_json(silent=True) or {}
    normalized_template, template_error = _normalize_template_payload(payload.get('template'), designer_mode='team_event')
    if template_error:
        return jsonify({'erro': template_error}), 400

    preview_data = payload.get('preview_data') or {}
    if not isinstance(preview_data, dict):
        return jsonify({'erro': 'preview_data deve ser um objeto'}), 400

    preview_recipient = SimpleNamespace(
        id=0,
        nome=str(preview_data.get('{{NOME}}') or 'Integrante Preview'),
        cpf=str(preview_data.get('{{CPF}}') or ''),
        email=None,
        role_label=str(preview_data.get('{{PAPEL}}') or 'Equipe'),
        workload_hours=str(preview_data.get('{{HORAS}}') or '0'),
        cert_hash=str(preview_data.get('{{HASH}}') or 'TEAMPREVIEWHASH'),
        activity=None,
    )
    pdf_path = team_cert_service.generate_recipient_pdf(
        event,
        preview_recipient,
        template_override=normalized_template,
        tag_overrides=preview_data,
    )
    return _build_pdf_preview_response(pdf_path)


@bp.route('/team/event/<int:event_id>/upload_asset', methods=['POST'])
@login_required
def upload_team_asset(event_id):
    event = _get_or_404(Event, event_id)
    if not _can_manage_certificates(event):
        return jsonify({'erro': 'Acesso negado para este evento'}), 403

    image_file = request.files.get('asset')
    valid_file, file_error = _validate_image_file(image_file)
    if not valid_file:
        return jsonify({'erro': file_error}), 400

    filename = secure_filename(f"asset_team_event_{event_id}_{image_file.filename}")
    upload_dir = os.path.join(current_app.root_path, 'static', 'certificates', 'assets')
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, filename)
    image_file.save(save_path)

    return jsonify({
        'mensagem': 'Asset enviado com sucesso',
        'asset_url': url_for('static', filename=f"certificates/assets/{filename}"),
        'asset_path': f"certificates/assets/{filename}",
    })


@bp.route('/team/download_public/<string:cert_hash>')
def download_team_public(cert_hash):
    recipient = EventTeamCertificateRecipient.query.filter_by(cert_hash=cert_hash).first()
    if not recipient:
        return "Certificado não encontrado", 404
    event = _event_for_team_recipient(recipient)
    if not event:
        return "Evento não encontrado", 404
    pdf_path = team_cert_service.generate_recipient_pdf(event, recipient)
    filename = f"Certificado_Equipe_{recipient.nome.replace(' ', '_')}.pdf"
    return send_file(pdf_path, as_attachment=True, download_name=filename)


@bp.route('/team/preview_public/<string:cert_hash>')
def preview_team_public(cert_hash):
    recipient = EventTeamCertificateRecipient.query.filter_by(cert_hash=cert_hash).first()
    if not recipient:
        return "Certificado não encontrado", 404
    event = _event_for_team_recipient(recipient)
    if not event:
        return "Evento não encontrado", 404
    pdf_path = team_cert_service.generate_recipient_pdf(event, recipient)
    return _build_pdf_preview_response(pdf_path)
