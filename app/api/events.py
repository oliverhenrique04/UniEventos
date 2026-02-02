from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import Event, Activity, db
from app.services.event_service import EventService
from app.serializers import serialize_event
from datetime import datetime

bp = Blueprint('events', __name__, url_prefix='/api')
event_service = EventService()

@bp.route('/criar_evento', methods=['POST'])
@login_required
def criar_evento():
    """
    Endpoint for creating a new event.
    Only professors and admins can create events.
    """
    if current_user.role == 'participante':
        return jsonify({"erro": "Negado"}), 403
    
    data = request.json
    
    # Simple validation for start date
    try:
        data_ini_obj = datetime.strptime(data.get('data_inicio'), '%Y-%m-%d').date()
        if data_ini_obj < datetime.now().date():
            return jsonify({"erro": "Data de início no passado!"}), 400
    except (ValueError, TypeError):
        pass

    try:
        event = event_service.create_event(current_user.username, data)
        return jsonify({"mensagem": "Criado!", "link": f"/inscrever/{event.token_publico}"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@bp.route('/editar_evento', methods=['POST'])
@login_required
def editar_evento():
    """
    Endpoint for updating an existing event.
    Only owners or admins can edit.
    """
    data = request.json
    evt_id = data.get('id')
    
    event, message = event_service.update_event(
        evt_id, current_user.username, current_user.role, data
    )
    
    if not event:
        status_code = 404 if message == "Evento não encontrado" else 403
        return jsonify({"erro": message}), status_code
        
    return jsonify({"mensagem": message})

@bp.route('/eventos_admin', methods=['GET'])
@login_required
def listar_eventos_admin():
    """Paginated and filtered list of all events for administrative purposes."""
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return jsonify([]), 403
    
    page = request.args.get('page', 1, type=int)
    filters = {
        'nome': request.args.get('nome'),
        'tipo': request.args.get('tipo'),
        'status': request.args.get('status'),
        'owner': request.args.get('owner')
    }
    
    pagination = event_service.list_events_paginated(page=page, filters=filters)
    
    return jsonify({
        "items": [serialize_event(e, current_user) for e in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })

@bp.route('/participantes_evento/<int:event_id>', methods=['GET'])
@login_required
def listar_participantes_evento(event_id):
    """Paginated and filtered list of participants in an event."""
    page = request.args.get('page', 1, type=int)
    filters = {
        'nome': request.args.get('nome'),
        'cpf': request.args.get('cpf'),
        'presente': request.args.get('presente', type=lambda v: v.lower() == 'true') if request.args.get('presente') else None
    }
    
    pagination = event_service.get_event_participants_paginated(event_id, page=page, filters=filters)
    
    return jsonify({
        "items": [{
            "id": e.id,
            "nome": e.nome,
            "cpf": e.user_cpf,
            "presente": e.presente,
            "atividade": e.activity.nome
        } for e in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })

@bp.route('/alternar_presenca/<int:enrollment_id>', methods=['POST'])
@login_required
def alternar_presenca_manual(enrollment_id):
    """Manually toggles the attendance status of a participant."""
    status = request.json.get('presente')
    success, msg = event_service.toggle_attendance_manual(enrollment_id, status)
    if success: return jsonify({"mensagem": msg})
    return jsonify({"erro": msg}), 400

@bp.route('/deletar_evento/<int:event_id>', methods=['DELETE'])
@login_required
def deletar_evento(event_id):
    """Removes an event and all its data."""
    success, msg = event_service.delete_event(event_id, current_user.username, current_user.role)
    if success: return jsonify({"mensagem": msg})
    return jsonify({"erro": msg}), 403

@bp.route('/remover_inscricao/<int:enrollment_id>', methods=['DELETE'])
@login_required
def remover_inscricao(enrollment_id):
    """Deletes a specific enrollment record."""
    from app.models import Enrollment, db
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    db.session.delete(enrollment)
    db.session.commit()
    return jsonify({"mensagem": "Inscrição removida!"})

@bp.route('/eventos', methods=['GET'])
@login_required
def listar_eventos():
    """Endpoint for listing events visible to the current user with pagination."""
    page = request.args.get('page', 1, type=int)
    pagination = event_service.get_events_for_user_paginated(current_user, page=page)
    
    return jsonify({
        "items": [serialize_event(e, current_user) for e in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })
