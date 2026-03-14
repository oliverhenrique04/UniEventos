from flask import Blueprint, render_template, redirect, url_for, abort, current_app
from flask_login import current_user, login_required
from datetime import datetime
from app.extensions import db


bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template(
            'login_register.html',
            moodle_login_enabled=current_app.config.get('MOODLE_LOGIN_ENABLED', False),
            moodle_login_url=current_app.config.get('MOODLE_LOGIN_URL', ''),
        )
    return render_template('dashboard.html', user=current_user)

@bp.route('/logout')
def logout():
    # This might be redundant if I have it in auth api, but usually logout is a GET link
    # I already defined /api/logout in auth.py which does logout_user() then redirects.
    # But the frontend has <a href="/logout">. So this route is needed.
    # I'll just redirect to the api logout or implement it here.
    return redirect(url_for('auth.logout'))


@bp.route('/resetar-senha/<token>')
def resetar_senha(token):
    return render_template('reset_password.html', token=token)

@bp.route('/inscrever/<token>')
def inscrever_via_link(token):
    """Public page to view event details via shared token link."""
    from app.repositories.event_repository import EventRepository
    repo = EventRepository()
    event = repo.get_by_token(token)
    
    if not event:
        return render_template('404.html'), 404
        
    return render_template('event_view.html', event=event, user=current_user)

@bp.route('/designer_certificado/<int:event_id>')
@login_required
def designer_certificado(event_id):
    """Page for visually designing and configuring certificates."""
    if current_user.role not in ['admin', 'coordenador', 'gestor']:
        return "Acesso negado", 403
    from app.models import Event
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    return render_template('certificate_designer.html', user=current_user, event=event)

@bp.route('/gerenciar_entregas/<int:event_id>')
@login_required
def gerenciar_entregas(event_id):
    """Page for managing individual certificate deliveries and status."""
    if current_user.role not in ['admin', 'coordenador', 'gestor']:
        return "Acesso negado", 403
    from app.models import Event
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    return render_template('certificate_delivery.html', user=current_user, event=event)


@bp.route('/certificados_institucionais')
@login_required
def certificados_institucionais_page():
    """Page for extension profile to manage institutional certificates."""
    if current_user.role not in ['admin', 'extensao', 'gestor']:
        return "Acesso negado", 403
    return render_template('institutional_certificates.html', user=current_user)


@bp.route('/designer_certificado_institucional/<int:certificate_id>')
@login_required
def designer_certificado_institucional(certificate_id):
    """Page for visually designing institutional certificates."""
    if current_user.role not in ['admin', 'extensao', 'gestor']:
        return "Acesso negado", 403

    from app.models import InstitutionalCertificate
    cert = db.session.get(InstitutionalCertificate, certificate_id)
    if not cert:
        abort(404)

    if current_user.role != 'admin' and cert.created_by_username != current_user.username:
        return "Acesso negado", 403

    return render_template('certificate_designer.html', user=current_user, event=cert, designer_mode='institutional')

@bp.route('/usuarios')
@login_required
def gerenciar_usuarios():
    """Page for full administrative user management CRUD."""
    if current_user.role != 'admin':
        return "Acesso negado", 403
    return render_template('users_admin.html', user=current_user)

@bp.route('/cursos')
@login_required
def gerenciar_cursos():
    """Page for full administrative course management CRUD."""
    if current_user.role not in ['admin', 'gestor']:
        return "Acesso negado", 403
    return render_template('courses_admin.html', user=current_user)

@bp.route('/confirmar_presenca/<int:atv_id>/<token_hash>')
@login_required
def confirmar_presenca_page(atv_id, token_hash):
    """Landing page for direct QR code scanning and presence confirmation."""
    from app.services.event_service import EventService
    service = EventService()
    activity = service.get_activity(atv_id)
    
    if not activity:
        return render_template('404.html'), 404
        
    return render_template('checkin_confirm.html', activity=activity, token=token_hash, user=current_user)

@bp.route('/eventos_admin')
@login_required
def gerenciar_eventos():
    """Page for full administrative event management CRUD and participant control."""
    if current_user.role not in ['admin', 'professor', 'coordenador', 'gestor']:
        return "Acesso negado", 403
    return render_template('events_admin.html', user=current_user)

@bp.route('/perfil')
@login_required
def perfil_usuario():
    """Page for user participation history and certificate collection."""
    return render_template('profile.html', user=current_user)

@bp.route('/meus_eventos')
@login_required
def meus_eventos():
    """Dedicated page for participants to see events they've already attended."""
    return render_template('my_events.html', user=current_user)

@bp.route('/criar_evento')
@login_required
def criar_evento_page():
    """Dedicated page for creating new events with multiple activities."""
    if current_user.role not in ['admin', 'professor', 'coordenador', 'gestor']:
        return "Acesso negado", 403
    return render_template('event_create.html', user=current_user)

@bp.route('/editar_evento/<int:event_id>')
@login_required
def editar_evento_page(event_id):
    """Page for editing an existing event."""
    if current_user.role not in ['admin', 'professor', 'coordenador', 'gestor']:
        return "Acesso negado", 403
    from app.models import Event
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    # Check permission
    if current_user.role != 'admin' and event.owner_username != current_user.username:
        return "Acesso negado", 403
    return render_template('event_edit.html', user=current_user, event=event)

@bp.route('/validar')
def validar_busca():
    """Public page to search and validate certificates by hash."""
    return render_template('validation.html')

@bp.route('/validar/<cert_hash>')
def validar_hash(cert_hash):
    """Public page to show validation results for a specific hash.
    
    Supports both event certificates and institutional certificates.
    """
    from app.models import Enrollment, Activity, Event, User, InstitutionalCertificateRecipient
    
    # Try to find institutional certificate first
    institutional_recipient = InstitutionalCertificateRecipient.query.filter_by(cert_hash=cert_hash).first()
    if institutional_recipient:
        cert = institutional_recipient.certificate
        
        # Format date
        data_br = cert.data_emissao
        try:
            data_br = datetime.strptime(cert.data_emissao, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            pass
        
        return render_template(
            'validation.html',
            success=True,
            certificado_tipo='institucional',  # Flag for institutional certificate
            nome=institutional_recipient.nome,
            evento=cert.titulo,
            data=data_br,
            horas=None,  # No hours for institutional certificates
            curso=cert.categoria if cert.categoria else 'N/A',
            signatario=cert.signer_name or 'N/A',
            cpf=institutional_recipient.cpf or 'N/A',
            hash=cert_hash,
        )
    
    # Try to find event certificate
    enrollment = Enrollment.query.filter_by(cert_hash=cert_hash).first()
    if not enrollment:
        return render_template('validation.html', erro="Certificado não encontrado ou inválido.")
    
    # Get activity and event details
    activity_ref = db.session.get(Activity, enrollment.activity_id)
    if not activity_ref:
        return render_template('validation.html', erro="Atividade relacionada não encontrada.")
    
    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    event = db.session.get(Event, activity_ref.event_id)
    curso = event.curso if event and event.curso else "N/A"
    
    # Calculate total hours for this user in this event
    from app.models import Enrollment as E2
    all_user_enrollments = E2.query.join(Activity, E2.activity_id == Activity.id).filter(
        Activity.event_id == activity_ref.event_id,
        E2.user_cpf == enrollment.user_cpf,
        E2.presente == True,
    ).all()
    
    total_hours = 0
    for e in all_user_enrollments:
        atv = db.session.get(Activity, e.activity_id)
        if atv:
            total_hours += (atv.carga_horaria or 0)
    
    # Format event date
    data_br = event.data_inicio.strftime("%d/%m/%Y") if event and event.data_inicio else ""
    
    return render_template(
        'validation.html',
        success=True,
        certificado_tipo='evento',  # Flag for event certificate
        nome=user.nome if user else enrollment.nome,
        evento=event.nome,
        data=data_br,
        horas=total_hours,
        curso=curso,
        signatario=None,  # No signer for event certificates
        cpf=enrollment.user_cpf,
        hash=cert_hash
    )
