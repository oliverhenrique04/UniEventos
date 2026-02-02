from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.services.certificate_service import CertificateService
from werkzeug.utils import secure_filename
import os

bp = Blueprint('certificates', __name__, url_prefix='/api/certificates')
cert_service = CertificateService()

@bp.route('/setup/<int:event_id>', methods=['POST'])
@login_required
def setup_certificate(event_id):
    """
    Configures the certificate background and template for an event.
    Expects a background image file and a template JSON string.
    """
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return jsonify({"erro": "Permissão negada"}), 403
        
    bg_file = request.files.get('background')
    template_json = request.form.get('template')
    remove_bg = request.form.get('remove_bg') == 'true'
    
    bg_path = None
    if remove_bg:
        bg_path = "" # Explicitly clear in service
    elif bg_file:
        filename = secure_filename(f"bg_event_{event_id}_{bg_file.filename}")
        upload_dir = os.path.join(current_app.root_path, 'static', 'certificates', 'backgrounds')
        os.makedirs(upload_dir, exist_ok=True)
        save_path = os.path.join(upload_dir, filename)
        bg_file.save(save_path)
        # Store as relative path for web access
        bg_path = f"certificates/backgrounds/{filename}"
    
    success = cert_service.update_config(event_id, bg_path, template_json)
    
    if success:
        return jsonify({
            "mensagem": "Configuração de certificado atualizada com sucesso!",
            "bg_url": f"/static/{bg_path}" if bg_path else None
        })
    return jsonify({"erro": "Falha ao atualizar configuração"}), 400

@bp.route('/send_batch/<int:event_id>', methods=['POST'])
@login_required
def send_batch(event_id):
    """Triggers the mass generation and queued delivery of certificates."""
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return jsonify({"erro": "Permissão negada"}), 403
    success, message = cert_service.queue_event_certificates(event_id)
    if success: return jsonify({"mensagem": message})
    return jsonify({"erro": message}), 400

@bp.route('/list_delivery/<int:event_id>', methods=['GET'])
@login_required
def list_delivery(event_id):
    """Lists all participants eligible for certificates with pagination."""
    from app.models import Enrollment, User
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
    from app.models import Enrollment, db
    new_email = request.json.get('email')
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    enrollment.cert_email_alternativo = new_email
    db.session.commit()
    return jsonify({"mensagem": "E-mail atualizado!"})

@bp.route('/resend_single/<int:enrollment_id>', methods=['POST'])
@login_required
def resend_single(enrollment_id):
    """Triggers a resend for a single certificate."""
    from app.models import Enrollment, Event, User, Activity
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    event = Event.query.get(enrollment.event_id)
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
    from app.models import Enrollment, Event, User, Activity
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    event = Event.query.get(enrollment.event_id)
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
    from app.models import Enrollment, Event, User, Activity
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    event = Event.query.get(enrollment.event_id)
    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    
    if not user: return "Usuário não encontrado", 404
    
    total_hours = 0
    presences = Enrollment.query.filter_by(event_id=event.id, user_cpf=user.cpf, presente=True).all()
    for p in presences:
        atv = Activity.query.get(p.activity_id)
        if atv: total_hours += (atv.carga_horaria or 0)

    from flask import send_file
    pdf_path = cert_service.generate_pdf(event, user, [], total_hours, enrollment=enrollment)
    
    # Send file without as_attachment=True to allow browser rendering
    return send_file(pdf_path, mimetype='application/pdf')
