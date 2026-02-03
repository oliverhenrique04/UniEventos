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
    Validates ownership or administrative privileges before proceeding.
    """
    data = request.json
    evt_id = data.get('id')
    
    if not evt_id:
        return jsonify({"erro": "ID do evento é obrigatório"}), 400
    
    try:
        event, message = event_service.update_event(
            evt_id, current_user.username, current_user.role, data
        )
        
        if not event:
            status_code = 404 if message == "Evento não encontrado" else 403
            return jsonify({"erro": message}), status_code
            
        return jsonify({"mensagem": message})
    except Exception as e:
        return jsonify({"erro": f"Erro interno ao atualizar evento: {str(e)}"}), 500

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
        'owner': request.args.get('owner'),
        'curso': request.args.get('curso'),
        'data': request.args.get('data')
    }
    
    pagination = event_service.list_events_paginated(page=page, filters=filters)
    
    return jsonify({
        "items": [serialize_event(e, current_user) for e in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })

@bp.route('/notificar_participantes/<int:event_id>', methods=['POST'])
@login_required
def notificar_participantes(event_id):
    """
    Sends a broadcast email notification to all participants of an event.
    Only authorized personnel (admin, professor, coordinator) can call this.
    """
    if current_user.role not in ['admin', 'professor', 'coordenador']:
        return jsonify({"erro": "Acesso negado"}), 403
    
    data = request.json
    subject = data.get('assunto')
    body = data.get('mensagem')
    
    if not subject or not body:
        return jsonify({"erro": "Assunto e mensagem são obrigatórios"}), 400
        
    try:
        count = event_service.notify_all_participants(event_id, subject, body)
        return jsonify({"mensagem": f"Notificação enfileirada para {count} participantes!"})
    except Exception as e:
        return jsonify({"erro": f"Erro ao processar notificações: {str(e)}"}), 500

@bp.route('/participantes_evento/<int:event_id>', methods=['GET'])
@login_required
def listar_participantes_evento(event_id):
    """Paginated and filtered list of participants in an event, including geofencing distance."""
    from app.utils import haversine_distance
    page = request.args.get('page', 1, type=int)
    filters = {
        'nome': request.args.get('nome'),
        'cpf': request.args.get('cpf'),
        'presente': request.args.get('presente', type=lambda v: v.lower() == 'true') if request.args.get('presente') else None
    }
    
    pagination = event_service.get_event_participants_paginated(event_id, page=page, filters=filters)
    
    items = []
    for e in pagination.items:
        # Calculate distance if we have both activity and check-in coordinates
        dist = None
        # Use activity coords if set, otherwise event coords
        ref_lat = e.activity.latitude if e.activity.latitude else e.activity.event.latitude
        ref_lon = e.activity.longitude if e.activity.longitude else e.activity.event.longitude
        
        if ref_lat and ref_lon and e.lat_checkin and e.lon_checkin:
            dist = haversine_distance(ref_lat, ref_lon, e.lat_checkin, e.lon_checkin)
        
        items.append({
            "id": e.id,
            "nome": e.nome,
            "cpf": e.user_cpf,
            "presente": e.presente,
            "atividade": e.activity.nome,
            "distancia": round(dist) if dist is not None else None,
            "lat_checkin": e.lat_checkin,
            "lon_checkin": e.lon_checkin
        })
    
    return jsonify({
        "items": items,
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

@bp.route('/me/history', methods=['GET'])
@login_required
def meu_historico():
    """Endpoint for the current user to retrieve their participation history and stats."""
    type = request.args.get('type', 'events') 
    page = request.args.get('page', 1, type=int)
    
    if type == 'stats':
        from app.models import Enrollment, Activity
        presences = Enrollment.query.filter_by(user_cpf=current_user.cpf, presente=True).all()
        total_hours = sum([Activity.query.get(p.activity_id).carga_horaria for p in presences if Activity.query.get(p.activity_id)])
        event_count = db.session.query(Enrollment.event_id).filter_by(user_cpf=current_user.cpf).distinct().count()
        return jsonify({"total_hours": total_hours, "total_events": event_count})

    if type == 'participated':
        from app.models import Event, Enrollment, Activity
        # Join Events with Enrollments where presente=True
        query = db.session.query(Event).join(Enrollment, Event.id == Enrollment.event_id)\
            .filter(Enrollment.user_cpf == current_user.cpf, Enrollment.presente == True).distinct()
        
        pagination = query.order_by(Event.data_inicio.desc()).paginate(page=page, per_page=10, error_out=False)
        
        items = []
        for ev in pagination.items:
            # Sum hours for this user in this event
            ev_hours = db.session.query(db.func.sum(Activity.carga_horaria))\
                .join(Enrollment, Activity.id == Enrollment.activity_id)\
                .filter(Enrollment.event_id == ev.id, Enrollment.user_cpf == current_user.cpf, Enrollment.presente == True).scalar() or 0
            
            items.append({
                "id": ev.id,
                "nome": ev.nome,
                "data": ev.data_inicio,
                "horas": int(ev_hours),
                "tipo": ev.tipo,
                "token": ev.token_publico
            })
        
        return jsonify({
            "items": items,
            "total": pagination.total,
            "pages": pagination.pages,
            "current_page": pagination.page
        })

    if type == 'events':
        pagination = event_service.get_user_events_paginated(current_user.cpf, page=page)
        items = [serialize_event(e, current_user) for e in pagination.items]
    elif type == 'activities':
        pagination = event_service.get_user_activities_paginated(current_user.cpf, page=page)
        items = [{
            "id": e.id,
            "atv_nome": e.activity.nome,
            "event_nome": e.activity.event.nome,
            "data": e.activity.data_atv,
            "horas": e.activity.carga_horaria,
            "presente": e.presente
        } for e in pagination.items]
    else: # certificates
        pagination = event_service.get_user_certificates_paginated(current_user.cpf, page=page)
        items = [{
            "enrollment_id": e.id,
            "atv_nome": e.activity.nome,
            "event_id": e.event_id,
            "event_nome": e.activity.event.nome,
            "data": e.activity.data_atv,
            "horas": e.activity.carga_horaria,
            "hash": e.cert_hash
        } for e in pagination.items]

    return jsonify({
        "items": items,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })

@bp.route('/eventos', methods=['GET'])
@login_required
def listar_eventos():
    """Endpoint for listing events visible to the current user with pagination and filters."""
    page = request.args.get('page', 1, type=int)
    filters = {
        'nome': request.args.get('nome'),
        'data': request.args.get('data'),
        'curso': request.args.get('curso')
    }
    pagination = event_service.get_events_for_user_paginated(current_user, page=page, filters=filters)
    
    return jsonify({
        "items": [serialize_event(e, current_user) for e in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    })
