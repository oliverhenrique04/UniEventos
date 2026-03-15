from flask import Blueprint, request, jsonify, current_app, abort, url_for
from flask_login import login_required, current_user
from app.services.certificate_service import CertificateService
from app.services.event_service import EventService
from werkzeug.utils import secure_filename
from threading import Lock, Thread
from uuid import uuid4
from types import SimpleNamespace
import os
import json
import re
import time

from app.models import Event, Enrollment, User, Activity
from app.extensions import db
from app.utils import build_absolute_app_url

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
MAX_DESIGN_IMAGE_SIZE = 8 * 1024 * 1024

bp = Blueprint('certificates', __name__, url_prefix='/api/certificates')
cert_service = CertificateService()
_SEND_BATCH_JOBS = {}
_SEND_BATCH_LOCK = Lock()


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
    return _can_manage_event(event)


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
    if not _can_manage_certificates(event):
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
    if not _can_manage_certificates(event):
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
    if not (_can_manage_certificates(event) or _can_access_own_certificate(enrollment)):
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
    if not (_can_manage_certificates(event) or _can_access_own_certificate(enrollment)):
        return "Acesso negado", 403

    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    
    if not user: return "Usuário não encontrado", 404
    
    cert_ctx = _certificate_context_for_enrollment(event, enrollment, user)

    pdf_path = cert_service.generate_pdf(event, user, [cert_ctx['activity']] if cert_ctx['activity'] else [], cert_ctx['hours'], enrollment=enrollment)
    return _build_pdf_preview_response(pdf_path)
