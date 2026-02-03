from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required
from datetime import datetime


bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('login_register.html')
    return render_template('dashboard.html', user=current_user)

@bp.route('/logout')
def logout():
    # This might be redundant if I have it in auth api, but usually logout is a GET link
    # I already defined /api/logout in auth.py which does logout_user() then redirects.
    # But the frontend has <a href="/logout">. So this route is needed.
    # I'll just redirect to the api logout or implement it here.
    return redirect('/api/logout')

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
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return "Acesso negado", 403
    from app.models import Event
    event = Event.query.get_or_404(event_id)
    return render_template('certificate_designer.html', user=current_user, event=event)

@bp.route('/gerenciar_entregas/<int:event_id>')
@login_required
def gerenciar_entregas(event_id):
    """Page for managing individual certificate deliveries and status."""
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return "Acesso negado", 403
    from app.models import Event
    event = Event.query.get_or_404(event_id)
    return render_template('certificate_delivery.html', user=current_user, event=event)

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
    if current_user.role != 'admin':
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
    if current_user.role not in ['admin', 'professor', 'coordenador']:
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
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return "Acesso negado", 403
    return render_template('event_create.html', user=current_user)

@bp.route('/editar_evento/<int:event_id>')
@login_required
def editar_evento_page(event_id):
    """Page for editing an existing event."""
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return "Acesso negado", 403
    from app.models import Event
    event = Event.query.get_or_404(event_id)
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
    """Public page to show validation results for a specific hash."""
    from app.models import Enrollment, Activity, Event, User
    enrollment = Enrollment.query.filter_by(cert_hash=cert_hash).first()
    if not enrollment:
        return render_template('validation.html', erro="Certificado não encontrado ou inválido.")
    
    # Calculate total hours for this user in this event
    # (Since hash is linked to one enrollment, but certificates are usually event-wide)
    # Actually, in our logic, one hash represents the participation in the event.
    activities = Activity.query.filter_by(event_id=enrollment.event_id).all()
    user = User.query.filter_by(cpf=enrollment.user_cpf).first()
    event = Event.query.get(enrollment.event_id)
    
    # Sum hours of activities where this user was present in this event
    total_hours = 0
    from app.models import Enrollment as E2
    all_user_enrollments = E2.query.filter_by(event_id=enrollment.event_id, user_cpf=enrollment.user_cpf, presente=True).all()
    for e in all_user_enrollments:
        atv = Activity.query.get(e.activity_id)
        if atv: total_hours += (atv.carga_horaria or 0)

    data_iso = event.data_inicio
    data_br = datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")

    return render_template('validation.html', 
                           success=True, 
                           nome=user.nome if user else enrollment.nome,
                           evento=event.nome,
                           data=data_br,
                           horas=total_hours,
                           hash=cert_hash)
