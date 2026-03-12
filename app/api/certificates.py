from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.services.certificate_service import CertificateService
from werkzeug.utils import secure_filename
import os
import json
import re

from app.models import Event, Enrollment, User, Activity

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


def _normalize_template(template_json):
    if template_json is None:
        return None, None

    try:
        parsed = json.loads(template_json)
    except (ValueError, TypeError):
        return None, "Template inválido: JSON malformado"

    if not isinstance(parsed, dict):
        return None, "Template inválido: estrutura esperada é um objeto"

    return json.dumps(parsed, ensure_ascii=False), None


def _can_manage_event(event):
    if current_user.role == 'admin':
        return True
    return event and event.owner_username == current_user.username


def _is_valid_email(email):
    if not email:
        return False
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None

@bp.route('/setup/<int:event_id>', methods=['POST'])
@login_required
def setup_certificate(event_id):
    """
    Configures the certificate background and template for an event.
    Expects a background image file and a template JSON string.
    """
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return jsonify({"erro": "Permissão negada"}), 403
        
    event = Event.query.get_or_404(event_id)
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
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return jsonify({"erro": "Permissão negada"}), 403

    event = Event.query.get_or_404(event_id)
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
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return jsonify({"erro": "Permissão negada"}), 403
    event = Event.query.get_or_404(event_id)
    if not _can_manage_event(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    success, message = cert_service.queue_event_certificates(event_id)
    if success: return jsonify({"mensagem": message})
    return jsonify({"erro": message}), 400

@bp.route('/list_delivery/<int:event_id>', methods=['GET'])
@login_required
def list_delivery(event_id):
    """Lists all participants eligible for certificates with pagination."""
    event = Event.query.get_or_404(event_id)
    if not _can_manage_event(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    pagination = Enrollment.query.filter_by(event_id=event_id, presente=True).paginate(page=page, per_page=per_page, error_out=False)
    
    res = []
    for e in pagination.items:
        user = User.query.filter_by(cpf=e.user_cpf).first()
        res.append({
            "enrollment_id": e.id,
            "nome": e.nome,
            "cpf": e.user_cpf,
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
    from app.models import db
    new_email = request.json.get('email')
    if not _is_valid_email(new_email):
        return jsonify({"erro": "E-mail inválido"}), 400

    enrollment = Enrollment.query.get_or_404(enrollment_id)
    event = Event.query.get(enrollment.event_id)
    if not _can_manage_event(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    enrollment.cert_email_alternativo = new_email
    db.session.commit()
    return jsonify({"mensagem": "E-mail atualizado!"})

@bp.route('/resend_single/<int:enrollment_id>', methods=['POST'])
@login_required
def resend_single(enrollment_id):
    """Triggers a resend for a single certificate."""
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    event = Event.query.get(enrollment.event_id)
    if not _can_manage_event(event):
        return jsonify({"erro": "Acesso negado para este evento"}), 403

    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    
    if not user: return jsonify({"erro": "Usuário não encontrado"}), 404
    
    # Calculate total hours
    total_hours = 0
    presences = Enrollment.query.filter_by(event_id=event.id, user_cpf=user.cpf, presente=True).all()
    for p in presences:
        atv = Activity.query.get(p.activity_id)
        if atv: total_hours += (atv.carga_horaria or 0)

    target_email = enrollment.cert_email_alternativo or user.email
    if not target_email: return jsonify({"erro": "E-mail não definido"}), 400

    # Generate and Queue
    pdf_path = cert_service.generate_pdf(event, user, [], total_hours, enrollment=enrollment)
    cert_service.notifier.send_email_task(
        to_email=target_email,
        subject=f"Reenvio de Certificado: {event.nome}",
        body=f"Olá {user.nome}, seu certificado de participação foi reenviado.",
        attachment_path=pdf_path
    )
    
    from datetime import datetime
    enrollment.cert_data_envio = datetime.now()
    enrollment.cert_entregue = True # Mark as initiated
    from app.extensions import db
    db.session.commit()
    
    return jsonify({"mensagem": "Reenvio solicitado!"})

@bp.route('/download/<int:enrollment_id>')
@login_required
def download_single(enrollment_id):
    # ... (Keep existing download_single code)
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    event = Event.query.get(enrollment.event_id)
    if not _can_manage_event(event):
        return "Acesso negado", 403

    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    if not user: return "Usuário não encontrado", 404
    total_hours = 0
    presences = Enrollment.query.filter_by(event_id=event.id, user_cpf=user.cpf, presente=True).all()
    for p in presences:
        atv = Activity.query.get(p.activity_id)
        if atv: total_hours += (atv.carga_horaria or 0)
    from flask import send_file
    pdf_path = cert_service.generate_pdf(event, user, [], total_hours, enrollment=enrollment)
    return send_file(pdf_path, as_attachment=True, download_name=f"Certificado_{user.nome.replace(' ', '_')}.pdf")

@bp.route('/preview/<int:enrollment_id>')
@login_required
def preview_single(enrollment_id):
    """Generates and serves a certificate PDF for inline viewing (preview)."""
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    event = Event.query.get(enrollment.event_id)
    if not _can_manage_event(event):
        return "Acesso negado", 403

    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    
    if not user: return "Usuário não encontrado", 404
    
    total_hours = 0
    presences = Enrollment.query.filter_by(event_id=event.id, user_cpf=user.cpf, presente=True).all()
    for p in presences:
        atv = Activity.query.get(p.activity_id)
        if atv: total_hours += (atv.carga_horaria or 0)

    from flask import send_file
    pdf_path = cert_service.generate_pdf(event, user, [], total_hours, enrollment=enrollment)

    # Force fresh render in browser preview to avoid stale cached PDFs.
    response = send_file(pdf_path, mimetype='application/pdf', conditional=False, max_age=0)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
