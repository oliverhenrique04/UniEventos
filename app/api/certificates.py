from flask import Blueprint, request, jsonify, current_app, abort
from flask_login import login_required, current_user
from app.services.certificate_service import CertificateService
from werkzeug.utils import secure_filename
import os
import json
import re

from app.models import Event, Enrollment, User, Activity
from app.extensions import db

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
MAX_DESIGN_IMAGE_SIZE = 8 * 1024 * 1024

bp = Blueprint('certificates', __name__, url_prefix='/api/certificates')
cert_service = CertificateService()


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


def _normalize_template(template_json):
    if template_json is None:
        return None, None

    try:
        parsed = json.loads(template_json)
    except (ValueError, TypeError):
        return None, "Template inválido: JSON malformado"

    if not isinstance(parsed, dict):
        return None, "Template inválido: estrutura esperada é um objeto"

    # Sanitize HTML content in text elements that use the Jodit rich editor
    for element in parsed.get('elements', []):
        if element.get('is_html') and element.get('html_content'):
            element['html_content'] = _sanitize_html_content(element['html_content'])

    return json.dumps(parsed, ensure_ascii=False), None


def _can_manage_event(event):
    if current_user.role == 'admin':
        return True
    return event and event.owner_username == current_user.username


def _can_manage_certificates(event):
    if current_user.role not in ['admin', 'coordenador']:
        return False
    return _can_manage_event(event)


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
    if current_user.role not in ['admin', 'coordenador']:
        return jsonify({"erro": "Permissão negada"}), 403
        
    event = _get_or_404(Event, event_id)
    if not _can_manage_event(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    bg_file = request.files.get('background')
    template_json = request.form.get('template')
    remove_bg = request.form.get('remove_bg') == 'true'

    normalized_template, template_error = _normalize_template(template_json)
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
            "bg_url": f"/static/{bg_path}" if bg_path else None
        })
    return jsonify({"erro": "Falha ao atualizar configuração"}), 400


@bp.route('/upload_asset/<int:event_id>', methods=['POST'])
@login_required
def upload_asset(event_id):
    """Uploads an image asset for inline certificate elements."""
    if current_user.role not in ['admin', 'coordenador']:
        return jsonify({"erro": "Permissão negada"}), 403

    event = _get_or_404(Event, event_id)
    if not _can_manage_event(event):
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
        "asset_url": f"/static/certificates/assets/{filename}",
        "asset_path": f"certificates/assets/{filename}"
    })

@bp.route('/send_batch/<int:event_id>', methods=['POST'])
@login_required
def send_batch(event_id):
    """Triggers the mass generation and queued delivery of certificates."""
    if current_user.role not in ['admin', 'coordenador']:
        return jsonify({"erro": "Permissão negada"}), 403
    event = _get_or_404(Event, event_id)
    if not _can_manage_certificates(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    success, message = cert_service.queue_event_certificates(event_id)
    if success: return jsonify({"mensagem": message})
    return jsonify({"erro": message}), 400

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
            "palestrante": (activity.palestrante if activity and activity.palestrante else "-"),
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
    base_url = (current_app.config.get('BASE_URL') or '').rstrip('/')
    validation_url = f"{base_url}/validar/{enrollment.cert_hash}" if base_url and enrollment.cert_hash else ''
    download_url = f"{base_url}/api/certificates/download_public/{enrollment.cert_hash}" if base_url and enrollment.cert_hash else ''
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
            'view_certificate_url': f"{base_url}/api/certificates/preview_public/{enrollment.cert_hash}" if base_url and enrollment.cert_hash else '',
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

    from flask import send_file
    pdf_path = cert_service.generate_pdf(event, user, [cert_ctx['activity']] if cert_ctx['activity'] else [], cert_ctx['hours'], enrollment=enrollment)
    response = send_file(pdf_path, mimetype='application/pdf', conditional=False, max_age=0)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@bp.route('/download/<int:enrollment_id>')
@login_required
def download_single(enrollment_id):
    # ... (Keep existing download_single code)
    enrollment = _get_or_404(Enrollment, enrollment_id)
    event = _event_from_enrollment(enrollment)
    if not _can_manage_certificates(event):
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
    if not _can_manage_certificates(event):
        return "Acesso negado", 403

    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    
    if not user: return "Usuário não encontrado", 404
    
    cert_ctx = _certificate_context_for_enrollment(event, enrollment, user)

    from flask import send_file
    pdf_path = cert_service.generate_pdf(event, user, [cert_ctx['activity']] if cert_ctx['activity'] else [], cert_ctx['hours'], enrollment=enrollment)

    # Force fresh render in browser preview to avoid stale cached PDFs.
    response = send_file(pdf_path, mimetype='application/pdf', conditional=False, max_age=0)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
